//
//  ELM327Protocol.swift
//  AutotechScan
//
//  Created for Autotech AI
//  Copyright © 2026 Aurora Sentient. All rights reserved.
//

import Foundation

/// Handles ELM327/STN protocol communication
class ELM327Protocol {
    
    private let bluetoothManager: BluetoothManager
    private var isInitialized = false
    
    init(bluetoothManager: BluetoothManager) {
        self.bluetoothManager = bluetoothManager
    }
    
    // MARK: - Initialization
    
    /// Initialize the ELM327 adapter with standard settings
    func initialize() async throws {
        // Reset adapter
        _ = try await bluetoothManager.sendCommand("ATZ", timeout: 3.0)
        try await Task.sleep(nanoseconds: 500_000_000) // 500ms delay
        
        // Echo off
        _ = try await bluetoothManager.sendCommand("ATE0")
        
        // Line feeds off
        _ = try await bluetoothManager.sendCommand("ATL0")
        
        // Headers off (for cleaner responses)
        _ = try await bluetoothManager.sendCommand("ATH0")
        
        // Spaces off (compact output)
        _ = try await bluetoothManager.sendCommand("ATS0")
        
        // Auto protocol detection
        _ = try await bluetoothManager.sendCommand("ATSP0")
        
        // Adaptive timing auto 2
        _ = try await bluetoothManager.sendCommand("ATAT2")
        
        isInitialized = true
    }
    
    // MARK: - VIN Reading
    
    /// Read Vehicle Identification Number
    func readVIN() async throws -> String {
        // Mode 09 PID 02 - VIN
        let response = try await bluetoothManager.sendCommand("0902", timeout: 5.0)
        return parseVIN(response)
    }
    
    private func parseVIN(_ response: String) -> String {
        // VIN response comes in multiple frames
        // Format: 49 02 01 XX XX XX XX XX ...
        var vinBytes: [UInt8] = []
        
        let lines = response.components(separatedBy: .newlines)
        for line in lines {
            let cleaned = line.replacingOccurrences(of: " ", with: "")
            
            // Skip header bytes (49 02 XX)
            if cleaned.hasPrefix("4902") {
                let dataStart = cleaned.index(cleaned.startIndex, offsetBy: 6)
                let hexData = String(cleaned[dataStart...])
                
                // Convert hex pairs to bytes
                var index = hexData.startIndex
                while index < hexData.endIndex {
                    let nextIndex = hexData.index(index, offsetBy: 2, limitedBy: hexData.endIndex) ?? hexData.endIndex
                    let hexByte = String(hexData[index..<nextIndex])
                    if let byte = UInt8(hexByte, radix: 16), byte != 0 {
                        vinBytes.append(byte)
                    }
                    index = nextIndex
                }
            }
        }
        
        return String(bytes: vinBytes, encoding: .ascii) ?? ""
    }
    
    // MARK: - DTC Reading
    
    /// Read stored Diagnostic Trouble Codes
    func readDTCs() async throws -> [String] {
        // Mode 03 - Read stored DTCs
        let response = try await bluetoothManager.sendCommand("03", timeout: 5.0)
        return parseDTCs(response)
    }
    
    /// Read pending Diagnostic Trouble Codes
    func readPendingDTCs() async throws -> [String] {
        // Mode 07 - Read pending DTCs
        let response = try await bluetoothManager.sendCommand("07", timeout: 5.0)
        return parseDTCs(response)
    }
    
    /// Clear all DTCs and reset monitors
    func clearDTCs() async throws {
        // Mode 04 - Clear DTCs
        _ = try await bluetoothManager.sendCommand("04", timeout: 3.0)
    }
    
    private func parseDTCs(_ response: String) -> [String] {
        var dtcs: [String] = []
        
        // Clean the response
        let cleaned = response
            .replacingOccurrences(of: " ", with: "")
            .replacingOccurrences(of: "\r", with: "")
            .replacingOccurrences(of: "\n", with: "")
        
        // Response format: 43 XX XX YY YY ZZ ZZ ...
        // Each DTC is 2 bytes (4 hex chars)
        
        // Remove mode response header (43 for mode 03, 47 for mode 07)
        var data = cleaned
        if data.hasPrefix("43") || data.hasPrefix("47") {
            data = String(data.dropFirst(2))
        }
        
        // Parse DTC pairs
        var index = data.startIndex
        while index < data.endIndex {
            let endIndex = data.index(index, offsetBy: 4, limitedBy: data.endIndex) ?? data.endIndex
            let dtcHex = String(data[index..<endIndex])
            
            if dtcHex.count == 4, let dtc = decodeDTC(dtcHex), dtc != "P0000" {
                dtcs.append(dtc)
            }
            
            index = endIndex
        }
        
        return dtcs
    }
    
    private func decodeDTC(_ hex: String) -> String? {
        guard hex.count == 4,
              let firstByte = UInt8(String(hex.prefix(2)), radix: 16),
              let secondByte = UInt8(String(hex.suffix(2)), radix: 16) else {
            return nil
        }
        
        // First character: P, C, B, or U
        let typeMap: [UInt8: String] = [
            0: "P", 1: "P", 2: "P", 3: "P",  // Powertrain
            4: "C", 5: "C", 6: "C", 7: "C",  // Chassis
            8: "B", 9: "B", 10: "B", 11: "B", // Body
            12: "U", 13: "U", 14: "U", 15: "U" // Network
        ]
        
        let firstNibble = (firstByte >> 4) & 0x0F
        let prefix = typeMap[firstNibble] ?? "P"
        
        // Second character: 0-3
        let secondChar = (firstByte >> 2) & 0x03
        
        // Remaining characters
        let thirdChar = firstByte & 0x03
        let fourthFifth = String(format: "%02X", secondByte)
        
        return "\(prefix)\(secondChar)\(thirdChar)\(fourthFifth)"
    }
    
    // MARK: - PID Reading
    
    /// Read a specific OBD PID
    func readPID(_ pid: String) async throws -> [UInt8] {
        // Mode 01 for current data
        let command = "01\(pid)"
        let response = try await bluetoothManager.sendCommand(command)
        return parsePIDResponse(response, expectedPID: pid)
    }
    
    private func parsePIDResponse(_ response: String, expectedPID: String) -> [UInt8] {
        let cleaned = response
            .replacingOccurrences(of: " ", with: "")
            .replacingOccurrences(of: "\r", with: "")
            .replacingOccurrences(of: "\n", with: "")
        
        // Response format: 41 XX YY ZZ ...
        // 41 = mode 01 response, XX = PID, YY ZZ = data bytes
        guard cleaned.hasPrefix("41") else { return [] }
        
        let data = String(cleaned.dropFirst(4)) // Skip "41XX"
        var bytes: [UInt8] = []
        
        var index = data.startIndex
        while index < data.endIndex {
            let endIndex = data.index(index, offsetBy: 2, limitedBy: data.endIndex) ?? data.endIndex
            let hexByte = String(data[index..<endIndex])
            if let byte = UInt8(hexByte, radix: 16) {
                bytes.append(byte)
            }
            index = endIndex
        }
        
        return bytes
    }
    
    // MARK: - Common PIDs
    
    /// Read engine RPM (PID 0C)
    func readRPM() async throws -> Int {
        let bytes = try await readPID("0C")
        guard bytes.count >= 2 else { throw OBDError.invalidResponse }
        return (Int(bytes[0]) * 256 + Int(bytes[1])) / 4
    }
    
    /// Read vehicle speed in km/h (PID 0D)
    func readSpeed() async throws -> Int {
        let bytes = try await readPID("0D")
        guard bytes.count >= 1 else { throw OBDError.invalidResponse }
        return Int(bytes[0])
    }
    
    /// Read coolant temperature in °C (PID 05)
    func readCoolantTemp() async throws -> Int {
        let bytes = try await readPID("05")
        guard bytes.count >= 1 else { throw OBDError.invalidResponse }
        return Int(bytes[0]) - 40
    }
    
    /// Read engine load percentage (PID 04)
    func readEngineLoad() async throws -> Double {
        let bytes = try await readPID("04")
        guard bytes.count >= 1 else { throw OBDError.invalidResponse }
        return Double(bytes[0]) * 100.0 / 255.0
    }
    
    /// Read throttle position percentage (PID 11)
    func readThrottlePosition() async throws -> Double {
        let bytes = try await readPID("11")
        guard bytes.count >= 1 else { throw OBDError.invalidResponse }
        return Double(bytes[0]) * 100.0 / 255.0
    }
    
    /// Read fuel system status (PID 03)
    func readFuelSystemStatus() async throws -> String {
        let bytes = try await readPID("03")
        guard bytes.count >= 1 else { throw OBDError.invalidResponse }
        
        switch bytes[0] {
        case 1: return "Open loop - insufficient engine temp"
        case 2: return "Closed loop - using O2 sensor"
        case 4: return "Open loop - engine load/decel"
        case 8: return "Open loop - system failure"
        case 16: return "Closed loop - using O2 sensor, fault"
        default: return "Unknown"
        }
    }
    
    /// Read intake air temperature in °C (PID 0F)
    func readIntakeAirTemp() async throws -> Int {
        let bytes = try await readPID("0F")
        guard bytes.count >= 1 else { throw OBDError.invalidResponse }
        return Int(bytes[0]) - 40
    }
    
    /// Read MAF air flow rate in g/s (PID 10)
    func readMAF() async throws -> Double {
        let bytes = try await readPID("10")
        guard bytes.count >= 2 else { throw OBDError.invalidResponse }
        return (Double(bytes[0]) * 256.0 + Double(bytes[1])) / 100.0
    }
    
    /// Read fuel tank level percentage (PID 2F)
    func readFuelLevel() async throws -> Double {
        let bytes = try await readPID("2F")
        guard bytes.count >= 1 else { throw OBDError.invalidResponse }
        return Double(bytes[0]) * 100.0 / 255.0
    }
    
    /// Read battery voltage (ELM327 command, not OBD PID)
    func readBatteryVoltage() async throws -> Double {
        let response = try await bluetoothManager.sendCommand("ATRV")
        // Response format: "12.6V" or "12.6"
        let cleaned = response
            .replacingOccurrences(of: "V", with: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return Double(cleaned) ?? 0.0
    }
}
