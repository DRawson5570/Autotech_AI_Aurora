"""
Tests for ELM327 module.

These tests use mocked connections for unit testing without actual hardware.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Import module components
from addons.scan_tool.pids import (
    PIDRegistry,
    decode_pid,
    get_pid_by_name,
    PID_DEFINITIONS,
)
from addons.scan_tool.protocol import (
    OBDProtocol,
    DTC,
    get_dtc_description,
)
from addons.scan_tool.connection import (
    ConnectionType,
    ConnectionConfig,
    create_connection,
)


class TestPIDDecoding:
    """Test PID decoding functions."""
    
    def test_decode_rpm(self):
        """Test RPM decoding: (A*256 + B) / 4"""
        # 0x1000 (4096) = 1024 RPM
        data = bytes([0x10, 0x00])
        value = PIDRegistry.decode('RPM', data)
        assert value == 1024.0
        
        # 0x0FA0 (4000) = 1000 RPM
        data = bytes([0x0F, 0xA0])
        value = PIDRegistry.decode('RPM', data)
        assert value == 1000.0
    
    def test_decode_coolant_temp(self):
        """Test coolant temp decoding: A - 40"""
        # 0x50 (80) - 40 = 40°C
        data = bytes([0x50])
        value = PIDRegistry.decode('COOLANT_TEMP', data)
        assert value == 40.0
        
        # 0x28 (40) - 40 = 0°C
        data = bytes([0x28])
        value = PIDRegistry.decode('COOLANT_TEMP', data)
        assert value == 0.0
    
    def test_decode_fuel_trim(self):
        """Test fuel trim decoding: (A - 128) * 100 / 128"""
        # 128 = 0%
        data = bytes([128])
        value = PIDRegistry.decode('STFT_B1', data)
        assert abs(value) < 0.01
        
        # 192 = +50%
        data = bytes([192])
        value = PIDRegistry.decode('STFT_B1', data)
        assert abs(value - 50.0) < 0.1
        
        # 64 = -50%
        data = bytes([64])
        value = PIDRegistry.decode('STFT_B1', data)
        assert abs(value - (-50.0)) < 0.1
    
    def test_decode_speed(self):
        """Test speed decoding: direct value"""
        data = bytes([100])
        value = PIDRegistry.decode('SPEED', data)
        assert value == 100.0
    
    def test_decode_load(self):
        """Test engine load decoding: A * 100 / 255"""
        # 255 = 100%
        data = bytes([255])
        value = PIDRegistry.decode('LOAD', data)
        assert abs(value - 100.0) < 0.1
        
        # 127 = ~49.8%
        data = bytes([127])
        value = PIDRegistry.decode('LOAD', data)
        assert abs(value - 49.8) < 0.1
    
    def test_decode_maf(self):
        """Test MAF decoding: (A*256 + B) / 100"""
        # 0x0064 (100) / 100 = 1.0 g/s
        data = bytes([0x00, 0x64])
        value = PIDRegistry.decode('MAF', data)
        assert value == 1.0
    
    def test_decode_voltage(self):
        """Test voltage decoding: (A*256 + B) / 1000"""
        # 0x3200 (12800) / 1000 = 12.8V
        data = bytes([0x32, 0x00])
        value = PIDRegistry.decode('VOLTAGE', data)
        assert value == 12.8


class TestPIDRegistry:
    """Test PID registry functions."""
    
    def test_get_pid_by_name(self):
        """Test looking up PID by name."""
        assert get_pid_by_name('RPM') == 0x0C
        assert get_pid_by_name('COOLANT_TEMP') == 0x05
        assert get_pid_by_name('STFT_B1') == 0x06
    
    def test_get_pid_by_alias(self):
        """Test looking up PID by alias."""
        assert get_pid_by_name('ENGINE_RPM') == 0x0C
        assert get_pid_by_name('ECT') == 0x05
        assert get_pid_by_name('TPS') == 0x11
    
    def test_get_pid_case_insensitive(self):
        """Test case insensitivity."""
        assert get_pid_by_name('rpm') == 0x0C
        assert get_pid_by_name('Rpm') == 0x0C
        assert get_pid_by_name('coolant_temp') == 0x05
    
    def test_unknown_pid(self):
        """Test unknown PID returns None."""
        assert get_pid_by_name('UNKNOWN_PID_XYZ') is None
    
    def test_registry_get_by_number(self):
        """Test getting definition by number."""
        defn = PIDRegistry.get(0x0C)
        assert defn is not None
        assert defn.name == 'RPM'
    
    def test_registry_list_names(self):
        """Test listing all PID names."""
        names = PIDRegistry.list_names()
        assert 'RPM' in names
        assert 'COOLANT_TEMP' in names
        assert len(names) > 30  # Should have many PIDs defined


class TestDTCDecoding:
    """Test DTC decoding functions."""
    
    def test_dtc_description(self):
        """Test DTC description lookup."""
        assert 'Lean' in get_dtc_description('P0171')
        assert 'Rich' in get_dtc_description('P0172')
        assert 'Misfire' in get_dtc_description('P0300')
    
    def test_unknown_dtc(self):
        """Test unknown DTC returns default."""
        desc = get_dtc_description('P9999')
        assert 'Unknown' in desc
    
    def test_dtc_type(self):
        """Test DTC type property."""
        dtc = DTC(code='P0171')
        assert dtc.type.value == 'P'
        
        dtc = DTC(code='C0035')
        assert dtc.type.value == 'C'
        
        dtc = DTC(code='B0001')
        assert dtc.type.value == 'B'
        
        dtc = DTC(code='U0100')
        assert dtc.type.value == 'U'
    
    def test_dtc_manufacturer_specific(self):
        """Test manufacturer-specific DTC detection."""
        dtc = DTC(code='P0171')  # Generic
        assert not dtc.is_manufacturer_specific
        
        dtc = DTC(code='P1171')  # Manufacturer-specific
        assert dtc.is_manufacturer_specific


class TestProtocolParsing:
    """Test protocol response parsing."""
    
    def test_parse_dtc_response(self):
        """Test parsing DTC response."""
        # Create mock connection
        mock_conn = MagicMock()
        protocol = OBDProtocol(mock_conn)
        
        # Test parsing "43 01 71 01 74" -> P0171, P0174
        response = "43 01 71 01 74"
        dtcs = protocol._parse_dtcs(response)
        
        assert len(dtcs) == 2
        assert dtcs[0].code == 'P0171'
        assert dtcs[1].code == 'P0174'
    
    def test_parse_dtc_no_codes(self):
        """Test parsing empty DTC response."""
        mock_conn = MagicMock()
        protocol = OBDProtocol(mock_conn)
        
        # No DTCs: 43 00 00
        response = "43 00 00"
        dtcs = protocol._parse_dtcs(response)
        
        assert len(dtcs) == 0
    
    def test_decode_dtc_hex(self):
        """Test hex DTC decoding."""
        mock_conn = MagicMock()
        protocol = OBDProtocol(mock_conn)
        
        # P0171 = 0171
        assert protocol._decode_dtc('0171') == 'P0171'
        
        # P0420 = 0420
        assert protocol._decode_dtc('0420') == 'P0420'
        
        # C0035 = 4035
        assert protocol._decode_dtc('4035') == 'C0035'
        
        # U0100 = C100
        assert protocol._decode_dtc('C100') == 'U0100'


class TestConnectionFactory:
    """Test connection factory."""
    
    def test_create_wifi_connection(self):
        """Test creating WiFi connection."""
        conn = create_connection(ConnectionType.WIFI, '192.168.0.10:35000')
        assert conn is not None
        assert conn.config.connection_type == ConnectionType.WIFI
    
    def test_create_serial_connection(self):
        """Test creating serial connection."""
        conn = create_connection(ConnectionType.USB, '/dev/ttyUSB0')
        assert conn is not None
        assert conn.config.connection_type == ConnectionType.USB
    
    def test_create_bluetooth_connection(self):
        """Test creating Bluetooth connection."""
        conn = create_connection(ConnectionType.BLUETOOTH, '/dev/rfcomm0')
        assert conn is not None
        assert conn.config.connection_type == ConnectionType.BLUETOOTH


class TestIntegration:
    """Integration tests (require mocked service)."""
    
    @pytest.mark.asyncio
    async def test_service_lifecycle(self):
        """Test service connect/disconnect lifecycle."""
        from addons.scan_tool.service import ELM327Service
        
        service = ELM327Service()
        assert not service.connected
        
        # Would test actual connection here with mocked adapter
        # For now just verify the object is created properly
        assert service._connection is None
        assert service._protocol is None
    
    @pytest.mark.asyncio
    async def test_diagnostic_snapshot_structure(self):
        """Test diagnostic snapshot data structure."""
        from addons.scan_tool.service import DiagnosticSnapshot
        from datetime import datetime
        
        snapshot = DiagnosticSnapshot(
            timestamp=datetime.now(),
            vin='1J4PN2GK2CW123456',
            dtcs=[DTC(code='P0171', description='System Too Lean')],
            pending_dtcs=[],
            pids={},
            supported_pids=[0x04, 0x05, 0x0C],
        )
        
        # Test serialization
        data = snapshot.to_dict()
        assert data['vin'] == '1J4PN2GK2CW123456'
        assert len(data['dtcs']) == 1
        assert data['dtcs'][0]['code'] == 'P0171'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
