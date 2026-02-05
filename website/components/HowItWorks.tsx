import React from 'react';
import { Icons } from './Icons';
import { StepItem } from '../types';

const steps: StepItem[] = [
  {
    number: '01',
    title: 'Describe the Problem',
    description: 'Tell it what you\'re seeing—symptoms, codes, what you\'ve already checked. Just like talking to a senior tech.',
  },
  {
    number: '02',
    title: 'Get Expert Reasoning',
    description: 'The AI thinks through the problem with you. What to check first, what\'s common on this vehicle, what to rule out.',
  },
  {
    number: '03',
    title: 'Confirm & Continue',
    description: 'Report back what you find. The AI adapts, narrows the diagnosis, and guides you to the fix.',
  }
];

export const HowItWorks: React.FC = () => {
  return (
    <section id="how-it-works" className="py-24 bg-slate-950 relative overflow-hidden">
        {/* Decorative background element */}
        <div className="absolute left-1/2 top-0 transform -translate-x-1/2 w-full h-full max-w-7xl">
            <div className="absolute top-[20%] left-[10%] w-72 h-72 bg-brand-blue/5 rounded-full blur-3xl"></div>
            <div className="absolute bottom-[20%] right-[10%] w-96 h-96 bg-brand-orange/5 rounded-full blur-3xl"></div>
        </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="mb-16 md:text-center">
            <h2 className="text-base text-brand-blue font-semibold tracking-wide uppercase">How It Works</h2>
            <p className="mt-2 text-3xl leading-8 font-extrabold tracking-tight text-white sm:text-4xl">
                Think it through together
            </p>
        </div>

        <div className="relative">
          {/* Connector Line for Desktop */}
          <div className="hidden md:block absolute top-12 left-0 w-full h-0.5 bg-slate-900 -z-10"></div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
            {steps.map((step, index) => (
              <div key={index} className="relative bg-slate-900 md:bg-transparent p-6 md:p-0 rounded-xl border border-slate-800 md:border-none">
                <div className="flex flex-col items-center text-center">
                  <div className="flex items-center justify-center w-24 h-24 rounded-full bg-slate-900 border-4 border-slate-800 text-3xl font-bold text-brand-blue mb-6 shadow-xl relative z-10">
                    {step.number}
                  </div>
                  <h3 className="text-xl font-bold text-white mb-3">{step.title}</h3>
                  <p className="text-slate-400 leading-relaxed">
                    {step.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Use Case CTA */}
        <div className="mt-20 bg-gradient-to-r from-brand-blue/10 to-transparent rounded-2xl p-8 border border-brand-blue/20">
          <div className="md:flex md:items-center md:justify-between">
            <div className="flex items-center space-x-4">
              <div className="p-3 bg-brand-blue rounded-lg">
                <Icons.Smartphone className="h-8 w-8 text-white" />
              </div>
              <div>
                <h4 className="text-lg font-bold text-white">Mobile Ready</h4>
                <p className="text-slate-400 text-sm">Bring the knowledge right to the vehicle bay.</p>
              </div>
            </div>
            <div className="mt-6 md:mt-0">
               <a href="/auth" className="flex items-center text-white hover:text-brand-accent font-medium transition-colors">
                  Try it on your phone <Icons.ArrowRight className="ml-2 w-4 h-4" />
               </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};