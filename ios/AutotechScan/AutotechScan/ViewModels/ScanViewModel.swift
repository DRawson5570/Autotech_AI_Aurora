//
//  ScanViewModel.swift
//  AutotechScan
//
//  Created for Autotech AI
//  Copyright © 2026 Aurora Sentient. All rights reserved.
//

import Foundation
import Combine

@MainActor
class ScanViewModel: ObservableObject {
    
    // MARK: - Published Properties
    
    @Published var scanState: ScanState = .idle
    @Published var vin: String = ""
    @Published var vehicleInfo: VehicleInfo?
    @Published var dtcs: [DTCInfo] = []
    @Published var pendingDTCs: [DTCInfo] = []
    @Published var liveData: [LiveDataPoint] = []
    @Published var diagnosis: DiagnosisResult?
    @Published var isLiveMonitoring = false
    @Published var errorMessage: String?
    
    // MARK: - Dependencies
    
    var bluetoothManager: BluetoothManager?
    private var elm327: ELM327Protocol?
    private let apiClient = APIClient()
    private var liveDataTimer: Timer?
    
    // MARK: - Public Methods
    
    /// Perform a full vehicle scan
    func performFullScan() async {
        guard let bluetooth = bluetoothManager else {
            errorMessage = "Bluetooth not available"
            return
        }
        
        elm327 = ELM327Protocol(bluetoothManager: bluetooth)
        
        do {
            // Initialize adapter
            scanState = .initializing
            try await elm327?.initialize()
            
            // Read VIN
            scanState = .readingVIN
            if let vinString = try? await elm327?.readVIN(), !vinString.isEmpty {
                vin = vinString
                // Decode VIN for vehicle info
                if let info = try? await apiClient.decodeVIN(vinString) {
                    vehicleInfo = info
                }
            }
            
            // Read DTCs
            scanState = .readingDTCs
            if let storedDTCs = try? await elm327?.readDTCs() {
                dtcs = storedDTCs.map { DTCInfo.parse($0) }
            }
            
            if let pending = try? await elm327?.readPendingDTCs() {
                pendingDTCs = pending.map { DTCInfo.parse($0) }
            }
            
            // Read basic PIDs
            scanState = .readingPIDs
            await readBasicPIDs()
            
            scanState = .complete
            
            // Auto-diagnose if we have DTCs
            if !dtcs.isEmpty {
                await requestDiagnosis()
            }
            
        } catch {
            scanState = .error(error.localizedDescription)
            errorMessage = error.localizedDescription
        }
    }
    
    /// Read only DTCs (quick scan)
    func scanDTCsOnly() async {
        guard let bluetooth = bluetoothManager else {
            errorMessage = "Bluetooth not available"
            return
        }
        
        elm327 = ELM327Protocol(bluetoothManager: bluetooth)
        
        do {
            scanState = .initializing
            try await elm327?.initialize()
            
            scanState = .readingDTCs
            if let storedDTCs = try? await elm327?.readDTCs() {
                dtcs = storedDTCs.map { DTCInfo.parse($0) }
            }
            
            if let pending = try? await elm327?.readPendingDTCs() {
                pendingDTCs = pending.map { DTCInfo.parse($0) }
            }
            
            scanState = .complete
            
            if !dtcs.isEmpty {
                await requestDiagnosis()
            }
            
        } catch {
            scanState = .error(error.localizedDescription)
        }
    }
    
    /// Clear all DTCs
    func clearAllDTCs() async {
        guard let elm = elm327 else {
            errorMessage = "Not connected"
            return
        }
        
        do {
            try await elm.clearDTCs()
            dtcs = []
            pendingDTCs = []
            diagnosis = nil
        } catch {
            errorMessage = "Failed to clear codes: \(error.localizedDescription)"
        }
    }
    
    /// Start live data monitoring
    func startLiveMonitoring() {
        isLiveMonitoring = true
        
        liveDataTimer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.readBasicPIDs()
            }
        }
    }
    
    /// Stop live data monitoring
    func stopLiveMonitoring() {
        isLiveMonitoring = false
        liveDataTimer?.invalidate()
        liveDataTimer = nil
    }
    
    /// Request AI diagnosis from server
    func requestDiagnosis(symptoms: String? = nil) async {
        let dtcCodes = dtcs.map { $0.code }
        
        // Build PID dictionary
        var pids: [String: Double] = [:]
        for dataPoint in liveData {
            pids[dataPoint.name] = dataPoint.value
        }
        
        let request = DiagnosisRequest(
            dtcs: dtcCodes,
            pids: pids.isEmpty ? nil : pids,
            vin: vin.isEmpty ? nil : vin,
            symptoms: symptoms
        )
        
        do {
            let response = try await apiClient.diagnose(request: request)
            if response.success, let result = response.diagnosis {
                diagnosis = result
            } else {
                errorMessage = response.error ?? "Diagnosis failed"
            }
        } catch {
            errorMessage = "Failed to get diagnosis: \(error.localizedDescription)"
        }
    }
    
    // MARK: - Private Methods
    
    private func readBasicPIDs() async {
        guard let elm = elm327 else { return }
        
        var newData: [LiveDataPoint] = []
        let now = Date()
        
        // RPM
        if let rpm = try? await elm.readRPM() {
            newData.append(LiveDataPoint(
                name: "RPM",
                value: Double(rpm),
                unit: "rpm",
                min: 0,
                max: 8000,
                timestamp: now
            ))
        }
        
        // Speed
        if let speed = try? await elm.readSpeed() {
            newData.append(LiveDataPoint(
                name: "Speed",
                value: Double(speed),
                unit: "km/h",
                min: 0,
                max: 200,
                timestamp: now
            ))
        }
        
        // Coolant temp
        if let temp = try? await elm.readCoolantTemp() {
            newData.append(LiveDataPoint(
                name: "Coolant Temp",
                value: Double(temp),
                unit: "°C",
                min: -40,
                max: 150,
                timestamp: now
            ))
        }
        
        // Engine load
        if let load = try? await elm.readEngineLoad() {
            newData.append(LiveDataPoint(
                name: "Engine Load",
                value: load,
                unit: "%",
                min: 0,
                max: 100,
                timestamp: now
            ))
        }
        
        // Throttle position
        if let throttle = try? await elm.readThrottlePosition() {
            newData.append(LiveDataPoint(
                name: "Throttle",
                value: throttle,
                unit: "%",
                min: 0,
                max: 100,
                timestamp: now
            ))
        }
        
        // Battery voltage
        if let voltage = try? await elm.readBatteryVoltage() {
            newData.append(LiveDataPoint(
                name: "Battery",
                value: voltage,
                unit: "V",
                min: 10,
                max: 15,
                timestamp: now
            ))
        }
        
        liveData = newData
    }
}
