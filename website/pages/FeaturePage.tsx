import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { Icons } from '../components/Icons';

interface FeatureData {
  title: string;
  tagline: string;
  description: string;
  icon: React.ReactNode;
  benefits: string[];
  examples: { query: string; answer: string }[];
  relatedFeatures: string[];
}

const featureData: Record<string, FeatureData> = {
  'instant-specifications': {
    title: 'Instant Specifications',
    tagline: 'Every spec, one question away',
    description: 'Stop flipping through service manuals. Get fluid capacities, torque specs, gap settings, and more instantly by simply asking. Our AI pulls directly from OEM sources to give you accurate, verified specifications for any make and model.',
    icon: <Icons.Zap className="w-12 h-12" />,
    benefits: [
      'Fluid capacities for engine oil, transmission, coolant, and differentials',
      'Torque specifications for critical fasteners and components',
      'Gap settings for spark plugs and valve adjustments',
      'Filter part numbers and cross-references',
      'Tire pressures and wheel torque specs',
    ],
    examples: [
      {
        query: 'What are the fluid capacities for a 2019 Ford F-150 5.0L?',
        answer: 'Engine Oil: 8.8 qts with filter • Coolant: 15.1 qts • 10R80 Transmission: 13.1 qts'
      },
      {
        query: 'Spark plug gap for 2018 Honda Accord 2.0T?',
        answer: '0.028-0.031 inches (0.7-0.8 mm) - Use NGK DILKAR8A8 or equivalent'
      }
    ],
    relatedFeatures: ['wiring-diagrams', 'component-locations', 'labor-times']
  },
  'wiring-diagrams': {
    title: 'Wiring Diagrams',
    tagline: 'Trace any circuit, solve any electrical mystery',
    description: 'Electrical diagnostics made simple. Request wiring diagrams for any system and get pinpoint accurate schematics with connector locations, wire colors, and pin assignments. Our AI can even help you trace circuits and identify likely failure points.',
    icon: <Icons.Cpu className="w-12 h-12" />,
    benefits: [
      'Full system wiring schematics in high resolution',
      'Connector pinouts with wire colors and gauge',
      'Ground and power distribution diagrams',
      'Component location overlays',
      'Interactive circuit tracing assistance',
    ],
    examples: [
      {
        query: 'Show me the alternator wiring for a 2015 Chevy Silverado',
        answer: '[Delivers full charging system diagram with connector C105 pinout, showing B+, field, and sense circuits with wire colors]'
      },
      {
        query: 'Where does the fuel pump get its ground?',
        answer: 'G302 - Left rear of frame, near fuel tank mounting bracket. Common failure point - check for corrosion.'
      }
    ],
    relatedFeatures: ['dtc-analysis', 'component-locations', 'instant-specifications']
  },
  'dtc-analysis': {
    title: 'DTC Analysis',
    tagline: 'From code to fix in seconds',
    description: 'Input any diagnostic trouble code and get more than just a definition. Our AI analyzes the code in context, provides probable causes ranked by likelihood, testing procedures, and verified fix information from real-world repair data.',
    icon: <Icons.Search className="w-12 h-12" />,
    benefits: [
      'Full DTC definitions with manufacturer-specific context',
      'Probable causes ranked by statistical likelihood',
      'Step-by-step testing procedures',
      'Known fixes and TSB cross-references',
      'Freeze frame data interpretation',
    ],
    examples: [
      {
        query: 'P0171 on a 2016 Toyota Camry 2.5L - what should I check?',
        answer: 'System Too Lean (Bank 1): Top causes: 1) MAF sensor contamination (45%) 2) Intake manifold gasket leak (25%) 3) Vacuum leak at PCV valve (15%). Check: MAF readings at idle should be 2.5-4g/s.'
      },
      {
        query: 'Multiple cylinder misfires after timing chain replacement on N20 BMW',
        answer: 'Common cause: VANOS solenoid installation sequence error. Verify: Exhaust cam must be timed BEFORE intake. Check for codes 2A82 and 2A87.'
      }
    ],
    relatedFeatures: ['wiring-diagrams', 'tsb-lookup', 'instant-specifications']
  },
  'component-locations': {
    title: 'Component Locations',
    tagline: 'Stop hunting, start fixing',
    description: 'Every vehicle hides components differently. Get precise locations for sensors, modules, connectors, and hard-to-find parts. Our AI provides removal instructions and access procedures so you can get to the part without guesswork.',
    icon: <Icons.Search className="w-12 h-12" />,
    benefits: [
      'Exact component locations with reference points',
      'Step-by-step access and removal procedures',
      'Hidden fastener and clip locations',
      'Required tools and special procedures',
      'Photos and diagram references when available',
    ],
    examples: [
      {
        query: 'Where is the TCM on a 2017 Jeep Cherokee?',
        answer: 'Transmission Control Module is integrated into the valve body inside the transmission pan. Requires: pan removal, fluid drain. Note: TCM requires programming after replacement.'
      },
      {
        query: 'EVAP purge valve location on 2020 Hyundai Elantra',
        answer: 'Located on the intake manifold, driver side, beneath the engine cover. Access: Remove engine cover (3x 10mm bolts), disconnect electrical connector before removal.'
      }
    ],
    relatedFeatures: ['instant-specifications', 'labor-times', 'wiring-diagrams']
  },
  'labor-times': {
    title: 'Labor Times',
    tagline: 'Quote with confidence',
    description: 'Accurate labor time estimates are critical for profitability. Get standard labor times for any repair operation, with notes on related procedures and common add-ons. Our data integrates directly into your quoting workflow.',
    icon: <Icons.Clock className="w-12 h-12" />,
    benefits: [
      'Standard labor times from industry databases',
      'Overlap allowances for related repairs',
      'Diagnostic time guidelines',
      'Sublet vs. in-house decision support',
      'R&R vs. replacement time comparisons',
    ],
    examples: [
      {
        query: 'Labor time for water pump replacement on 2018 BMW X5 3.0T?',
        answer: 'Water Pump R&R: 3.2 hours. Add: Thermostat (+0.3 if included), Coolant flush (+0.4). Note: Electric water pump - requires ISTA activation after replacement.'
      },
      {
        query: 'How long to replace timing chain on 2015 Chevy Equinox 2.4?',
        answer: 'Timing Chain, Guides & Tensioner: 7.8 hours. Recommended adds: Oil pump drive chain (+0.5), Front cover reseal (included). Watch for: stretched chain causing VVT codes.'
      }
    ],
    relatedFeatures: ['instant-specifications', 'component-locations', 'tsb-lookup']
  },
  'tsb-lookup': {
    title: 'TSB Lookup',
    tagline: "Learn from others' repairs",
    description: "Technical Service Bulletins are goldmines of repair knowledge. Our AI automatically checks for relevant TSBs on every query and surfaces them when they match your diagnostic scenario. Don't reinvent the wheel - leverage manufacturer insights.",
    icon: <Icons.FileText className="w-12 h-12" />,
    benefits: [
      'Automatic TSB matching for vehicle queries',
      'Full TSB text with repair procedures',
      'Recall and campaign cross-references',
      'Pattern failure identification',
      'Parts supersession information',
    ],
    examples: [
      {
        query: 'Rough idle on cold start, 2019 Subaru Outback 2.5',
        answer: 'TSB 02-185-20: Cold Start Idle Roughness. Cause: PCV valve calibration. Fix: Reprogram ECM with latest calibration. No parts required. Warranty: Extension to 8yr/100k.'
      },
      {
        query: 'Any TSBs for AC compressor noise on 2021 Kia Sorento?',
        answer: 'TSB SSK081: A/C Compressor Noise. Applies to Sorento 2021-2022 with R1234yf. Fix: Replace compressor with updated Part# 97701-XXXXX. Pre-auth required.'
      }
    ],
    relatedFeatures: ['dtc-analysis', 'instant-specifications', 'labor-times']
  }
};

const featureSlugToTitle: Record<string, string> = {
  'instant-specifications': 'Instant Specifications',
  'wiring-diagrams': 'Wiring Diagrams',
  'dtc-analysis': 'DTC Analysis',
  'component-locations': 'Component Locations',
  'labor-times': 'Labor Times',
  'tsb-lookup': 'TSB Lookup',
};

export const FeaturePage: React.FC = () => {
  const { slug } = useParams<{ slug: string }>();
  const feature = slug ? featureData[slug] : null;

  if (!feature) {
    return (
      <div className="pt-32 pb-24 px-4 text-center">
        <h1 className="text-4xl font-bold text-white mb-4">Feature Not Found</h1>
        <Link to="/" className="text-brand-blue hover:text-brand-accent transition-colors">
          ← Back to Home
        </Link>
      </div>
    );
  }

  return (
    <div className="pt-24 pb-16 lg:pt-32">
      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-16">
        <Link 
          to="/#features" 
          className="inline-flex items-center text-slate-400 hover:text-brand-blue transition-colors mb-8"
        >
          <Icons.ArrowRight className="w-4 h-4 rotate-180 mr-2" />
          Back to Features
        </Link>
        
        <div className="flex items-start gap-6 mb-6">
          <div className="p-4 bg-gradient-to-br from-brand-blue to-blue-600 rounded-xl shadow-lg text-white">
            {feature.icon}
          </div>
          <div>
            <h1 className="text-4xl md:text-5xl font-extrabold text-white mb-2">
              {feature.title}
            </h1>
            <p className="text-xl text-brand-accent">{feature.tagline}</p>
          </div>
        </div>
        
        <p className="text-lg text-slate-400 max-w-3xl leading-relaxed">
          {feature.description}
        </p>

        {/* Related Features - inline for easy navigation */}
        <div className="mt-8 pt-8 border-t border-slate-800">
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-4">Related Capabilities</h3>
          <div className="flex flex-wrap gap-3">
            {feature.relatedFeatures.map((relatedSlug) => {
              const related = featureData[relatedSlug];
              if (!related) return null;
              return (
                <Link
                  key={relatedSlug}
                  to={`/features/${relatedSlug}`}
                  className="inline-flex items-center gap-2 bg-slate-900 px-4 py-2 rounded-lg border border-slate-800 hover:border-brand-blue/50 transition-colors group"
                >
                  <span className="text-brand-blue">{React.cloneElement(related.icon as React.ReactElement, { className: 'w-4 h-4' })}</span>
                  <span className="text-sm text-slate-300 group-hover:text-white transition-colors">{related.title}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      {/* Benefits Section */}
      <section className="bg-slate-900 py-16 mb-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-white mb-8">What You Get</h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {feature.benefits.map((benefit, index) => (
              <div 
                key={index}
                className="flex items-start gap-3 bg-slate-950 p-4 rounded-xl border border-slate-800"
              >
                <Icons.CheckCircle2 className="w-5 h-5 text-brand-blue mt-0.5 flex-shrink-0" />
                <span className="text-slate-300">{benefit}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Examples Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-16">
        <h2 className="text-2xl font-bold text-white mb-8">See It In Action</h2>
        <div className="space-y-6">
          {feature.examples.map((example, index) => (
            <div 
              key={index}
              className="bg-slate-900 rounded-2xl border border-slate-800 overflow-hidden"
            >
              {/* Query */}
              <div className="p-4 border-b border-slate-800 bg-slate-950">
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-slate-800 rounded-lg">
                    <Icons.MessageSquare className="w-4 h-4 text-slate-400" />
                  </div>
                  <p className="text-white font-medium pt-1">{example.query}</p>
                </div>
              </div>
              {/* Answer */}
              <div className="p-4">
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-brand-blue/20 rounded-lg">
                    <Icons.Cpu className="w-4 h-4 text-brand-blue" />
                  </div>
                  <p className="text-slate-300 pt-1 leading-relaxed">{example.answer}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-gradient-to-r from-brand-blue/20 to-brand-dark/20 rounded-2xl p-8 md:p-12 border border-brand-blue/30 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">Ready to Try It?</h2>
          <p className="text-slate-400 mb-8 max-w-xl mx-auto">
            Start asking questions about any vehicle and get expert answers instantly.
          </p>
          <a
            href="https://automotive.aurora-sentient.net"
            className="inline-flex items-center justify-center px-8 py-4 border border-transparent text-base font-medium rounded-full text-white bg-brand-blue hover:bg-cyan-600 transition-all shadow-lg hover:shadow-brand-blue/25"
          >
            <Icons.Zap className="w-5 h-5 mr-2" />
            Start Diagnosis Now
          </a>
        </div>
      </section>
    </div>
  );
};
