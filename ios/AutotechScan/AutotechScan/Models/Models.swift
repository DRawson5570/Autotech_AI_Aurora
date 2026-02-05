//
//  Models.swift
//  AutotechScan
//
//  Created for Autotech AI
//  Copyright © 2026 Aurora Sentient. All rights reserved.
//

import Foundation

// MARK: - Diagnosis Request/Response

struct DiagnosisRequest: Codable {
    let dtcs: [String]
    let pids: [String: Double]?
    let vin: String?
    let symptoms: String?
    
    enum CodingKeys: String, CodingKey {
        case dtcs
        case pids
        case vin
        case symptoms
    }
}

struct DiagnosisResponse: Codable {
    let success: Bool
    let diagnosis: DiagnosisResult?
    let error: String?
}

struct DiagnosisResult: Codable {
    let summary: String
    let probableCauses: [ProbableCause]
    let recommendations: [String]
    let urgency: String
    
    enum CodingKeys: String, CodingKey {
        case summary
        case probableCauses = "probable_causes"
        case recommendations
        case urgency
    }
}

struct ProbableCause: Codable, Identifiable {
    var id: String { name }
    let name: String
    let confidence: Double
    let description: String
}

// MARK: - Vehicle Info

struct VehicleInfo: Codable {
    let vin: String
    let year: Int?
    let make: String?
    let model: String?
    let engine: String?
    let trim: String?
}

// MARK: - Live Data

struct LiveDataPoint: Identifiable {
    let id = UUID()
    let name: String
    let value: Double
    let unit: String
    let min: Double
    let max: Double
    let timestamp: Date
    
    var formattedValue: String {
        if value == value.rounded() {
            return "\(Int(value)) \(unit)"
        } else {
            return String(format: "%.1f %@", value, unit)
        }
    }
    
    var percentage: Double {
        guard max > min else { return 0 }
        return (value - min) / (max - min)
    }
}

// MARK: - DTC Info

struct DTCInfo: Identifiable {
    var id: String { code }
    let code: String
    let description: String
    let severity: DTCSeverity
    let system: String
    
    static func parse(_ code: String) -> DTCInfo {
        let (description, system, severity) = lookupDTC(code)
        return DTCInfo(
            code: code,
            description: description,
            severity: severity,
            system: system
        )
    }
    
    private static func lookupDTC(_ code: String) -> (String, String, DTCSeverity) {
        // Basic DTC lookup - the server provides full descriptions
        let prefix = code.prefix(1)
        let system: String
        
        switch prefix {
        case "P":
            system = "Powertrain"
        case "C":
            system = "Chassis"
        case "B":
            system = "Body"
        case "U":
            system = "Network"
        default:
            system = "Unknown"
        }
        
        // Common DTCs with descriptions
        let knownDTCs: [String: (String, DTCSeverity)] = [
            "P0300": ("Random/Multiple Cylinder Misfire", .high),
            "P0301": ("Cylinder 1 Misfire", .high),
            "P0302": ("Cylinder 2 Misfire", .high),
            "P0303": ("Cylinder 3 Misfire", .high),
            "P0304": ("Cylinder 4 Misfire", .high),
            "P0420": ("Catalyst System Efficiency Below Threshold", .medium),
            "P0171": ("System Too Lean (Bank 1)", .medium),
            "P0172": ("System Too Rich (Bank 1)", .medium),
            "P0174": ("System Too Lean (Bank 2)", .medium),
            "P0175": ("System Too Rich (Bank 2)", .medium),
            "P0440": ("Evaporative Emission System Malfunction", .low),
            "P0442": ("Evaporative Emission System Leak (Small)", .low),
            "P0455": ("Evaporative Emission System Leak (Large)", .medium),
            "P0128": ("Coolant Thermostat Below Regulating Temperature", .medium),
            "P0401": ("EGR Flow Insufficient", .medium),
            "P0500": ("Vehicle Speed Sensor Malfunction", .medium),
            "P0700": ("Transmission Control System Malfunction", .high),
            "P0715": ("Input/Turbine Speed Sensor Circuit", .high),
        ]
        
        if let known = knownDTCs[code] {
            return (known.0, system, known.1)
        }
        
        return ("Unknown code - check with technician", system, .medium)
    }
}

enum DTCSeverity: String, Codable {
    case low = "low"
    case medium = "medium"
    case high = "high"
    
    var color: String {
        switch self {
        case .low: return "yellow"
        case .medium: return "orange"
        case .high: return "red"
        }
    }
}

// MARK: - Scan State

enum ScanState {
    case idle
    case initializing
    case readingVIN
    case readingDTCs
    case readingPIDs
    case complete
    case error(String)
    
    var description: String {
        switch self {
        case .idle: return "Ready"
        case .initializing: return "Initializing adapter..."
        case .readingVIN: return "Reading VIN..."
        case .readingDTCs: return "Reading trouble codes..."
        case .readingPIDs: return "Reading sensor data..."
        case .complete: return "Scan complete"
        case .error(let msg): return "Error: \(msg)"
        }
    }
}
