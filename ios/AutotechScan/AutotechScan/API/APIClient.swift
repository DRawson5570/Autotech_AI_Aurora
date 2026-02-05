//
//  APIClient.swift
//  AutotechScan
//
//  Created for Autotech AI
//  Copyright © 2026 Aurora Sentient. All rights reserved.
//

import Foundation

/// Client for communicating with Autotech AI server
class APIClient {
    
    // MARK: - Configuration
    
    #if DEBUG
    private let baseURL = "https://automotive.aurora-sentient.net"
    #else
    private let baseURL = "https://automotive.aurora-sentient.net"
    #endif
    
    private let session: URLSession
    
    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 60
        self.session = URLSession(configuration: config)
    }
    
    // MARK: - Diagnosis
    
    /// Send scan data to server for AI diagnosis
    func diagnose(request: DiagnosisRequest) async throws -> DiagnosisResponse {
        let url = URL(string: "\(baseURL)/api/v1/scan/diagnose")!
        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let encoder = JSONEncoder()
        urlRequest.httpBody = try encoder.encode(request)
        
        let (data, response) = try await session.data(for: urlRequest)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
        
        let decoder = JSONDecoder()
        return try decoder.decode(DiagnosisResponse.self, from: data)
    }
    
    // MARK: - VIN Decode
    
    /// Decode a VIN to get vehicle information
    func decodeVIN(_ vin: String) async throws -> VehicleInfo {
        let url = URL(string: "\(baseURL)/api/v1/scan/vin/decode?vin=\(vin)")!
        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "GET"
        
        let (data, response) = try await session.data(for: urlRequest)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError(statusCode: httpResponse.statusCode)
        }
        
        let decoder = JSONDecoder()
        return try decoder.decode(VehicleInfo.self, from: data)
    }
}

// MARK: - Error Types

enum APIError: Error, LocalizedError {
    case invalidResponse
    case serverError(statusCode: Int)
    case decodingError(Error)
    case networkError(Error)
    
    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from server"
        case .serverError(let statusCode):
            return "Server error: \(statusCode)"
        case .decodingError(let error):
            return "Failed to decode response: \(error.localizedDescription)"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        }
    }
}
