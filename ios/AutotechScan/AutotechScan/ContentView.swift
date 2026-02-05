//
//  ContentView.swift
//  AutotechScan
//
//  Created for Autotech AI
//  Copyright © 2026 Aurora Sentient. All rights reserved.
//

import SwiftUI

struct ContentView: View {
    @EnvironmentObject var bluetoothManager: BluetoothManager
    @StateObject private var viewModel = ScanViewModel()
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Header
                headerView
                
                // Main content
                if bluetoothManager.isConnected {
                    ScanView(viewModel: viewModel)
                } else {
                    connectionView
                }
            }
            .background(Color(.systemGroupedBackground))
        }
        .onAppear {
            viewModel.bluetoothManager = bluetoothManager
        }
    }
    
    private var headerView: some View {
        HStack {
            Image(systemName: "car.fill")
                .font(.title2)
                .foregroundColor(.blue)
            
            Text("Autotech Scan")
                .font(.title2)
                .fontWeight(.bold)
            
            Spacer()
            
            // Connection status indicator
            HStack(spacing: 6) {
                Circle()
                    .fill(bluetoothManager.isConnected ? Color.green : Color.red)
                    .frame(width: 10, height: 10)
                
                Text(bluetoothManager.isConnected ? "Connected" : "Disconnected")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding()
        .background(Color(.systemBackground))
    }
    
    private var connectionView: some View {
        VStack(spacing: 24) {
            Spacer()
            
            // Scanner icon
            Image(systemName: "antenna.radiowaves.left.and.right")
                .font(.system(size: 80))
                .foregroundColor(.blue)
            
            Text("Connect to OBD2 Scanner")
                .font(.title2)
                .fontWeight(.semibold)
            
            Text("Make sure your OBDLink MX+ or compatible scanner is powered on and in range")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            
            // Device list
            if !bluetoothManager.discoveredDevices.isEmpty {
                VStack(alignment: .leading, spacing: 12) {
                    Text("Available Devices")
                        .font(.headline)
                        .padding(.horizontal)
                    
                    ForEach(bluetoothManager.discoveredDevices, id: \.identifier) { device in
                        Button {
                            bluetoothManager.connect(to: device)
                        } label: {
                            HStack {
                                Image(systemName: "car.circle.fill")
                                    .font(.title2)
                                    .foregroundColor(.blue)
                                
                                VStack(alignment: .leading) {
                                    Text(device.name ?? "Unknown Device")
                                        .font(.body)
                                        .foregroundColor(.primary)
                                    
                                    Text(device.identifier.uuidString.prefix(8) + "...")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                                
                                Spacer()
                                
                                if bluetoothManager.isConnecting {
                                    ProgressView()
                                } else {
                                    Image(systemName: "chevron.right")
                                        .foregroundColor(.secondary)
                                }
                            }
                            .padding()
                            .background(Color(.systemBackground))
                            .cornerRadius(12)
                        }
                        .disabled(bluetoothManager.isConnecting)
                    }
                }
                .padding()
            }
            
            // Scan button
            Button {
                if bluetoothManager.isScanning {
                    bluetoothManager.stopScanning()
                } else {
                    bluetoothManager.startScanning()
                }
            } label: {
                HStack {
                    if bluetoothManager.isScanning {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        Text("Scanning...")
                    } else {
                        Image(systemName: "magnifyingglass")
                        Text("Scan for Devices")
                    }
                }
                .font(.headline)
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding()
                .background(bluetoothManager.isScanning ? Color.orange : Color.blue)
                .cornerRadius(12)
            }
            .padding(.horizontal, 40)
            
            // Error message
            if let error = bluetoothManager.errorMessage {
                Text(error)
                    .font(.caption)
                    .foregroundColor(.red)
                    .padding()
            }
            
            Spacer()
        }
    }
}

#Preview {
    ContentView()
        .environmentObject(BluetoothManager())
}
