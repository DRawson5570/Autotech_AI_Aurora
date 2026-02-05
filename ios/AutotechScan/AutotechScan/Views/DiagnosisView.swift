//
//  DiagnosisView.swift
//  AutotechScan
//
//  Created for Autotech AI
//  Copyright © 2026 Aurora Sentient. All rights reserved.
//

import SwiftUI

struct DiagnosisView: View {
    let diagnosis: DiagnosisResult
    
    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            // Urgency banner
            urgencyBanner
            
            // Summary
            VStack(alignment: .leading, spacing: 8) {
                Label("Summary", systemImage: "doc.text")
                    .font(.headline)
                
                Text(diagnosis.summary)
                    .font(.body)
                    .foregroundColor(.secondary)
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(.systemBackground))
            .cornerRadius(12)
            
            // Probable causes
            VStack(alignment: .leading, spacing: 12) {
                Label("Probable Causes", systemImage: "exclamationmark.triangle")
                    .font(.headline)
                
                ForEach(diagnosis.probableCauses) { cause in
                    ProbableCauseRow(cause: cause)
                }
            }
            .padding()
            .background(Color(.systemBackground))
            .cornerRadius(12)
            
            // Recommendations
            VStack(alignment: .leading, spacing: 12) {
                Label("Recommendations", systemImage: "wrench.and.screwdriver")
                    .font(.headline)
                
                ForEach(Array(diagnosis.recommendations.enumerated()), id: \.offset) { index, recommendation in
                    HStack(alignment: .top, spacing: 12) {
                        Text("\(index + 1).")
                            .font(.subheadline)
                            .foregroundColor(.blue)
                            .fontWeight(.semibold)
                        
                        Text(recommendation)
                            .font(.subheadline)
                    }
                }
            }
            .padding()
            .background(Color(.systemBackground))
            .cornerRadius(12)
            
            Spacer()
        }
        .padding()
    }
    
    private var urgencyBanner: some View {
        HStack {
            Image(systemName: urgencyIcon)
                .font(.title2)
            
            VStack(alignment: .leading) {
                Text("Urgency Level")
                    .font(.caption)
                    .opacity(0.8)
                Text(diagnosis.urgency.capitalized)
                    .font(.headline)
                    .fontWeight(.bold)
            }
            
            Spacer()
        }
        .padding()
        .foregroundColor(.white)
        .background(urgencyColor)
        .cornerRadius(12)
    }
    
    private var urgencyColor: Color {
        switch diagnosis.urgency.lowercased() {
        case "low": return .green
        case "medium": return .orange
        case "high", "critical": return .red
        default: return .blue
        }
    }
    
    private var urgencyIcon: String {
        switch diagnosis.urgency.lowercased() {
        case "low": return "checkmark.shield"
        case "medium": return "exclamationmark.triangle"
        case "high", "critical": return "exclamationmark.octagon"
        default: return "info.circle"
        }
    }
}

struct ProbableCauseRow: View {
    let cause: ProbableCause
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(cause.name)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                
                Spacer()
                
                // Confidence badge
                Text("\(Int(cause.confidence * 100))%")
                    .font(.caption)
                    .fontWeight(.bold)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(confidenceColor.opacity(0.2))
                    .foregroundColor(confidenceColor)
                    .cornerRadius(8)
            }
            
            Text(cause.description)
                .font(.caption)
                .foregroundColor(.secondary)
            
            // Confidence bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Rectangle()
                        .fill(Color(.systemGray5))
                        .frame(height: 4)
                        .cornerRadius(2)
                    
                    Rectangle()
                        .fill(confidenceColor)
                        .frame(width: geometry.size.width * cause.confidence, height: 4)
                        .cornerRadius(2)
                }
            }
            .frame(height: 4)
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(8)
    }
    
    private var confidenceColor: Color {
        if cause.confidence >= 0.7 { return .red }
        if cause.confidence >= 0.4 { return .orange }
        return .yellow
    }
}

#Preview {
    DiagnosisView(diagnosis: DiagnosisResult(
        summary: "Multiple misfires detected indicating potential ignition or fuel system issues.",
        probableCauses: [
            ProbableCause(name: "Worn Spark Plugs", confidence: 0.85, description: "Spark plugs may be worn or fouled, causing inconsistent ignition."),
            ProbableCause(name: "Ignition Coil Failure", confidence: 0.65, description: "One or more ignition coils may be failing intermittently."),
            ProbableCause(name: "Fuel Injector Issue", confidence: 0.40, description: "Clogged or malfunctioning fuel injector.")
        ],
        recommendations: [
            "Inspect and replace spark plugs if worn",
            "Test ignition coils with multimeter",
            "Check fuel pressure and injector spray pattern",
            "Perform compression test if issue persists"
        ],
        urgency: "medium"
    ))
}
