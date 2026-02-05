//
//  ScanView.swift
//  AutotechScan
//
//  Created for Autotech AI
//  Copyright © 2026 Aurora Sentient. All rights reserved.
//

import SwiftUI

struct ScanView: View {
    @ObservedObject var viewModel: ScanViewModel
    @State private var selectedTab = 0
    @State private var showingSymptomSheet = false
    @State private var symptomText = ""
    
    var body: some View {
        VStack(spacing: 0) {
            // Status bar
            statusBar
            
            // Tab picker
            Picker("View", selection: $selectedTab) {
                Text("DTCs").tag(0)
                Text("Live Data").tag(1)
                Text("Diagnosis").tag(2)
            }
            .pickerStyle(.segmented)
            .padding()
            
            // Content
            TabView(selection: $selectedTab) {
                dtcView.tag(0)
                liveDataView.tag(1)
                diagnosisView.tag(2)
            }
            .tabViewStyle(.page(indexDisplayMode: .never))
            
            // Action buttons
            actionButtons
        }
        .sheet(isPresented: $showingSymptomSheet) {
            symptomInputSheet
        }
    }
    
    // MARK: - Status Bar
    
    private var statusBar: some View {
        HStack {
            // Vehicle info
            VStack(alignment: .leading, spacing: 2) {
                if let info = viewModel.vehicleInfo {
                    Text("\(info.year ?? 0) \(info.make ?? "") \(info.model ?? "")")
                        .font(.headline)
                    if !viewModel.vin.isEmpty {
                        Text("VIN: \(viewModel.vin)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                } else if !viewModel.vin.isEmpty {
                    Text("VIN: \(viewModel.vin)")
                        .font(.subheadline)
                } else {
                    Text("No vehicle info")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }
            
            Spacer()
            
            // Scan state
            VStack(alignment: .trailing, spacing: 2) {
                Text(viewModel.scanState.description)
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                if !viewModel.dtcs.isEmpty {
                    Text("\(viewModel.dtcs.count) DTCs")
                        .font(.caption)
                        .foregroundColor(.red)
                        .fontWeight(.semibold)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
    }
    
    // MARK: - DTC View
    
    private var dtcView: some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                if viewModel.dtcs.isEmpty && viewModel.pendingDTCs.isEmpty {
                    emptyDTCView
                } else {
                    // Stored DTCs
                    if !viewModel.dtcs.isEmpty {
                        Section {
                            ForEach(viewModel.dtcs) { dtc in
                                DTCCard(dtc: dtc)
                            }
                        } header: {
                            SectionHeader(title: "Stored Codes", count: viewModel.dtcs.count)
                        }
                    }
                    
                    // Pending DTCs
                    if !viewModel.pendingDTCs.isEmpty {
                        Section {
                            ForEach(viewModel.pendingDTCs) { dtc in
                                DTCCard(dtc: dtc, isPending: true)
                            }
                        } header: {
                            SectionHeader(title: "Pending Codes", count: viewModel.pendingDTCs.count)
                        }
                    }
                }
            }
            .padding()
        }
    }
    
    private var emptyDTCView: some View {
        VStack(spacing: 16) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 60))
                .foregroundColor(.green)
            
            Text("No Trouble Codes")
                .font(.title2)
                .fontWeight(.semibold)
            
            Text("Your vehicle has no stored diagnostic trouble codes")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding(.top, 60)
    }
    
    // MARK: - Live Data View
    
    private var liveDataView: some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                if viewModel.liveData.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "gauge")
                            .font(.system(size: 60))
                            .foregroundColor(.blue)
                        
                        Text("No Live Data")
                            .font(.title2)
                        
                        Text("Run a scan or start live monitoring")
                            .foregroundColor(.secondary)
                    }
                    .padding(.top, 60)
                } else {
                    ForEach(viewModel.liveData) { dataPoint in
                        LiveDataCard(dataPoint: dataPoint)
                    }
                }
            }
            .padding()
        }
    }
    
    // MARK: - Diagnosis View
    
    private var diagnosisView: some View {
        ScrollView {
            if let diagnosis = viewModel.diagnosis {
                DiagnosisView(diagnosis: diagnosis)
            } else {
                VStack(spacing: 16) {
                    Image(systemName: "stethoscope")
                        .font(.system(size: 60))
                        .foregroundColor(.purple)
                    
                    Text("No Diagnosis Yet")
                        .font(.title2)
                    
                    Text("Scan your vehicle to get AI-powered diagnostics")
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                    
                    if !viewModel.dtcs.isEmpty {
                        Button("Get Diagnosis") {
                            Task {
                                await viewModel.requestDiagnosis()
                            }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                }
                .padding(.top, 60)
                .padding(.horizontal)
            }
        }
    }
    
    // MARK: - Action Buttons
    
    private var actionButtons: some View {
        HStack(spacing: 12) {
            // Full Scan
            Button {
                Task {
                    await viewModel.performFullScan()
                }
            } label: {
                Label("Full Scan", systemImage: "magnifyingglass")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .disabled(viewModel.scanState != .idle && viewModel.scanState != .complete)
            
            // Live Monitor
            Button {
                if viewModel.isLiveMonitoring {
                    viewModel.stopLiveMonitoring()
                } else {
                    viewModel.startLiveMonitoring()
                }
            } label: {
                Label(
                    viewModel.isLiveMonitoring ? "Stop" : "Live",
                    systemImage: viewModel.isLiveMonitoring ? "stop.fill" : "waveform"
                )
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .tint(viewModel.isLiveMonitoring ? .red : .blue)
            
            // Clear Codes
            if !viewModel.dtcs.isEmpty {
                Button {
                    Task {
                        await viewModel.clearAllDTCs()
                    }
                } label: {
                    Label("Clear", systemImage: "trash")
                }
                .buttonStyle(.bordered)
                .tint(.red)
            }
        }
        .padding()
        .background(Color(.systemBackground))
    }
    
    // MARK: - Symptom Input Sheet
    
    private var symptomInputSheet: some View {
        NavigationStack {
            VStack(spacing: 16) {
                Text("Describe the symptoms you're experiencing")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                TextEditor(text: $symptomText)
                    .frame(minHeight: 150)
                    .padding(8)
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                
                Text("Example: Car hesitates when accelerating, rough idle when cold")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Spacer()
            }
            .padding()
            .navigationTitle("Add Symptoms")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        showingSymptomSheet = false
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Submit") {
                        showingSymptomSheet = false
                        Task {
                            await viewModel.requestDiagnosis(symptoms: symptomText)
                        }
                    }
                    .disabled(symptomText.isEmpty)
                }
            }
        }
    }
}

// MARK: - Supporting Views

struct SectionHeader: View {
    let title: String
    let count: Int
    
    var body: some View {
        HStack {
            Text(title)
                .font(.headline)
            
            Text("\(count)")
                .font(.caption)
                .padding(.horizontal, 8)
                .padding(.vertical, 2)
                .background(Color.red)
                .foregroundColor(.white)
                .cornerRadius(10)
            
            Spacer()
        }
        .padding(.top, 8)
    }
}

struct DTCCard: View {
    let dtc: DTCInfo
    var isPending = false
    
    var body: some View {
        HStack(spacing: 12) {
            // Severity indicator
            Circle()
                .fill(severityColor)
                .frame(width: 12, height: 12)
            
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(dtc.code)
                        .font(.headline)
                        .fontWeight(.bold)
                    
                    if isPending {
                        Text("PENDING")
                            .font(.caption2)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.orange.opacity(0.2))
                            .foregroundColor(.orange)
                            .cornerRadius(4)
                    }
                }
                
                Text(dtc.description)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                Text(dtc.system)
                    .font(.caption)
                    .foregroundColor(.blue)
            }
            
            Spacer()
            
            Image(systemName: "chevron.right")
                .foregroundColor(.secondary)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
    }
    
    private var severityColor: Color {
        switch dtc.severity {
        case .low: return .yellow
        case .medium: return .orange
        case .high: return .red
        }
    }
}

struct LiveDataCard: View {
    let dataPoint: LiveDataPoint
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(dataPoint.name)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                
                Spacer()
                
                Text(dataPoint.formattedValue)
                    .font(.title2)
                    .fontWeight(.semibold)
            }
            
            // Progress bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Rectangle()
                        .fill(Color(.systemGray5))
                        .frame(height: 8)
                        .cornerRadius(4)
                    
                    Rectangle()
                        .fill(progressColor)
                        .frame(width: geometry.size.width * dataPoint.percentage, height: 8)
                        .cornerRadius(4)
                }
            }
            .frame(height: 8)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
    }
    
    private var progressColor: Color {
        let pct = dataPoint.percentage
        if pct < 0.3 { return .green }
        if pct < 0.7 { return .yellow }
        return .red
    }
}

#Preview {
    ScanView(viewModel: ScanViewModel())
}
