import React from 'react';
import { Icons } from './Icons';
import { FeatureItem } from '../types';

const features: FeatureItem[] = [
  {
    title: '"What should I check first?"',
    description: 'Guided diagnosis based on symptoms. Get a systematic approach to narrowing down the problem, not just a list of possibilities.',
    icon: <Icons.Search className="w-6 h-6" />,
  },
  {
    title: '"What usually goes wrong?"',
    description: 'Known issues and common failures by vehicle. Learn what experienced techs have seen on this exact year/make/model.',
    icon: <Icons.Zap className="w-6 h-6" />,
  },
  {
    title: '"What does this code mean?"',
    description: 'DTC interpretation plus probable causes and next steps. Not just the definition—the diagnostic path forward.',
    icon: <Icons.Cpu className="w-6 h-6" />,
  },
  {
    title: '"Am I on the right track?"',
    description: 'Second opinion on your diagnosis. Describe what you\'ve found and get confirmation or alternative directions to investigate.',
    icon: <Icons.CheckCircle2 className="w-6 h-6" />,
  },
  {
    title: '"Explain this system to me"',
    description: 'Understand how any automotive system works—stability control, EVAP, CAN bus, whatever. The kind of knowledge that makes you a better tech.',
    icon: <Icons.Cpu className="w-6 h-6" />,
  },
  {
    title: '"How do I do this?"',
    description: 'Procedure walkthroughs and tips from the field. The kind of guidance you\'d get from a mentor looking over your shoulder.',
    icon: <Icons.FileText className="w-6 h-6" />,
  },
];

export const Features: React.FC = () => {
  return (
    <section id="features" className="py-24 bg-slate-900 relative">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-base text-brand-blue font-semibold tracking-wide uppercase">What You Can Ask</h2>
          <p className="mt-2 text-3xl leading-8 font-extrabold tracking-tight text-white sm:text-4xl">
            The questions that actually matter
          </p>
          <p className="mt-4 max-w-2xl text-xl text-slate-400 mx-auto">
            Not just data lookup—real diagnostic thinking. The kind of help you'd get from a veteran tech who's seen it all.
          </p>
        </div>

        <div className="mt-20">
          <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature, index) => (
              <div key={index} className="pt-6">
                <div className="flow-root bg-slate-950 rounded-2xl px-6 pb-8 border border-slate-800 h-full">
                  <div className="-mt-6">
                    <div>
                      <span className="inline-flex items-center justify-center p-3 bg-gradient-to-br from-brand-blue to-blue-600 rounded-md shadow-lg">
                        <div className="text-white">
                            {feature.icon}
                        </div>
                      </span>
                    </div>
                    <h3 className="mt-8 text-lg font-medium text-white tracking-tight">{feature.title}</h3>
                    <p className="mt-5 text-base text-slate-400 leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};