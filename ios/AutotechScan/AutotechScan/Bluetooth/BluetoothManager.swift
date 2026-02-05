//
//  BluetoothManager.swift
//  AutotechScan
//
//  Created for Autotech AI
//  Copyright © 2026 Aurora Sentient. All rights reserved.
//

import Foundation
import CoreBluetooth
import Combine

/// Manages Bluetooth Low Energy connections to OBD2 adapters
class BluetoothManager: NSObject, ObservableObject {
    
    // MARK: - Published Properties
    
    @Published var isScanning = false
    @Published var isConnecting = false
    @Published var isConnected = false
    @Published var discoveredDevices: [CBPeripheral] = []
    @Published var errorMessage: String?
    
    // MARK: - Private Properties
    
    private var centralManager: CBCentralManager!
    private var connectedPeripheral: CBPeripheral?
    private var obdCharacteristic: CBCharacteristic?
    
    // ELM327/OBDLink UUIDs - Standard BLE OBD Service
    private let obdServiceUUID = CBUUID(string: "FFE0")
    private let obdCharacteristicUUID = CBUUID(string: "FFE1")
    
    // Alternative UUIDs for different adapters
    private let altServiceUUIDs = [
        CBUUID(string: "FFF0"),  // Some Chinese adapters
        CBUUID(string: "E7810A71-73AE-499D-8C15-FAA9AEF0C3F2"),  // OBDLink specific
    ]
    
    // Response handling
    private var responseBuffer = ""
    private var responseCompletion: ((String) -> Void)?
    private var responseTimer: Timer?
    
    // MARK: - Initialization
    
    override init() {
        super.init()
        centralManager = CBCentralManager(delegate: self, queue: nil)
    }
    
    // MARK: - Public Methods
    
    /// Start scanning for OBD2 devices
    func startScanning() {
        guard centralManager.state == .poweredOn else {
            errorMessage = "Bluetooth is not available"
            return
        }
        
        discoveredDevices.removeAll()
        isScanning = true
        errorMessage = nil
        
        // Scan for known OBD service UUIDs
        var serviceUUIDs = [obdServiceUUID] + altServiceUUIDs
        centralManager.scanForPeripherals(withServices: nil, options: [
            CBCentralManagerScanOptionAllowDuplicatesKey: false
        ])
        
        // Auto-stop scanning after 10 seconds
        DispatchQueue.main.asyncAfter(deadline: .now() + 10) { [weak self] in
            self?.stopScanning()
        }
    }
    
    /// Stop scanning for devices
    func stopScanning() {
        centralManager.stopScan()
        isScanning = false
    }
    
    /// Connect to a specific peripheral
    func connect(to peripheral: CBPeripheral) {
        stopScanning()
        isConnecting = true
        errorMessage = nil
        connectedPeripheral = peripheral
        centralManager.connect(peripheral, options: nil)
    }
    
    /// Disconnect from the current peripheral
    func disconnect() {
        if let peripheral = connectedPeripheral {
            centralManager.cancelPeripheralConnection(peripheral)
        }
        cleanup()
    }
    
    /// Send a command to the OBD adapter and wait for response
    func sendCommand(_ command: String, timeout: TimeInterval = 2.0) async throws -> String {
        guard let characteristic = obdCharacteristic,
              let peripheral = connectedPeripheral else {
            throw OBDError.notConnected
        }
        
        return try await withCheckedThrowingContinuation { continuation in
            responseBuffer = ""
            
            // Set up response handler
            responseCompletion = { [weak self] response in
                self?.responseTimer?.invalidate()
                continuation.resume(returning: response)
            }
            
            // Set up timeout
            responseTimer = Timer.scheduledTimer(withTimeInterval: timeout, repeats: false) { [weak self] _ in
                let buffer = self?.responseBuffer ?? ""
                self?.responseCompletion = nil
                if buffer.isEmpty {
                    continuation.resume(throwing: OBDError.timeout)
                } else {
                    continuation.resume(returning: buffer)
                }
            }
            
            // Send the command with carriage return
            let commandWithCR = command + "\r"
            if let data = commandWithCR.data(using: .utf8) {
                peripheral.writeValue(data, for: characteristic, type: .withResponse)
            }
        }
    }
    
    // MARK: - Private Methods
    
    private func cleanup() {
        connectedPeripheral = nil
        obdCharacteristic = nil
        isConnected = false
        isConnecting = false
        responseBuffer = ""
        responseCompletion = nil
        responseTimer?.invalidate()
    }
}

// MARK: - CBCentralManagerDelegate

extension BluetoothManager: CBCentralManagerDelegate {
    
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        switch central.state {
        case .poweredOn:
            errorMessage = nil
        case .poweredOff:
            errorMessage = "Bluetooth is turned off"
            cleanup()
        case .unauthorized:
            errorMessage = "Bluetooth permission denied"
        case .unsupported:
            errorMessage = "Bluetooth is not supported on this device"
        default:
            break
        }
    }
    
    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral, advertisementData: [String : Any], rssi RSSI: NSNumber) {
        // Filter for likely OBD devices by name
        let name = peripheral.name?.lowercased() ?? ""
        let obdKeywords = ["obd", "elm", "vlink", "carista", "veepeak", "bafx", "bluedriver", "konnwei"]
        
        // Accept devices with OBD-related names or any device with the OBD service
        let isLikelyOBD = obdKeywords.contains { name.contains($0) }
        
        if isLikelyOBD || peripheral.name != nil {
            if !discoveredDevices.contains(where: { $0.identifier == peripheral.identifier }) {
                DispatchQueue.main.async {
                    self.discoveredDevices.append(peripheral)
                }
            }
        }
    }
    
    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        isConnecting = false
        peripheral.delegate = self
        peripheral.discoverServices([obdServiceUUID] + altServiceUUIDs)
    }
    
    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        errorMessage = "Failed to connect: \(error?.localizedDescription ?? "Unknown error")"
        cleanup()
    }
    
    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        if error != nil {
            errorMessage = "Disconnected: \(error?.localizedDescription ?? "")"
        }
        cleanup()
    }
}

// MARK: - CBPeripheralDelegate

extension BluetoothManager: CBPeripheralDelegate {
    
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard error == nil else {
            errorMessage = "Service discovery failed: \(error!.localizedDescription)"
            return
        }
        
        for service in peripheral.services ?? [] {
            peripheral.discoverCharacteristics([obdCharacteristicUUID], for: service)
        }
    }
    
    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        guard error == nil else {
            errorMessage = "Characteristic discovery failed: \(error!.localizedDescription)"
            return
        }
        
        for characteristic in service.characteristics ?? [] {
            if characteristic.uuid == obdCharacteristicUUID || 
               characteristic.properties.contains(.notify) {
                obdCharacteristic = characteristic
                peripheral.setNotifyValue(true, for: characteristic)
                
                DispatchQueue.main.async {
                    self.isConnected = true
                }
            }
        }
    }
    
    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        guard error == nil,
              let data = characteristic.value,
              let response = String(data: data, encoding: .utf8) else {
            return
        }
        
        responseBuffer += response
        
        // Check for prompt character indicating end of response
        if responseBuffer.contains(">") {
            let finalResponse = responseBuffer
                .replacingOccurrences(of: ">", with: "")
                .trimmingCharacters(in: .whitespacesAndNewlines)
            
            responseCompletion?(finalResponse)
            responseCompletion = nil
            responseBuffer = ""
        }
    }
}

// MARK: - Error Types

enum OBDError: Error, LocalizedError {
    case notConnected
    case timeout
    case invalidResponse
    case noData
    
    var errorDescription: String? {
        switch self {
        case .notConnected:
            return "Not connected to OBD adapter"
        case .timeout:
            return "Command timed out"
        case .invalidResponse:
            return "Invalid response from adapter"
        case .noData:
            return "No data available"
        }
    }
}
