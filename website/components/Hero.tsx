import React, { useState, useEffect } from 'react';
import { Icons } from './Icons';

export const Hero: React.FC = () => {
  const [typedText, setTypedText] = useState('');
  const [showResponse, setShowResponse] = useState(true); // Show immediately - no layout shift
  
  const query = "My 2015 Malibu is running rough and has code P0300. What should I check first?";

  useEffect(() => {
    let currentIndex = 0;
    const typingInterval = setInterval(() => {
      if (currentIndex <= query.length) {
        setTypedText(query.slice(0, currentIndex));
        currentIndex++;
      } else {
        clearInterval(typingInterval);
      }
    }, 40);

    return () => clearInterval(typingInterval);
  }, []);

  return (
    <div className="relative pt-24 pb-16 lg:pt-32 lg:pb-24 overflow-hidden">
      {/* Hero image LEFT - fades into background */}
      <div className="absolute top-0 left-0 w-full lg:w-1/2 h-full -z-10 hidden lg:block">
        <img 
          src="/images/hero-tech.jpg" 
          alt="Automotive technician using tablet" 
          className="w-full h-full object-cover object-center"
        />
        {/* Lighter gradient overlays - matched with right side */}
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-slate-950/30 to-slate-950" />
        <div className="absolute inset-0 bg-gradient-to-b from-slate-950/20 via-transparent to-slate-950/60" />
        <div className="absolute inset-0 bg-slate-950/20" />
      </div>

      {/* Hero image RIGHT - shop background */}
      <div className="absolute top-0 right-0 w-full lg:w-1/2 h-full -z-10 hidden lg:block">
        <img 
          src="/images/shop-bg.jpg" 
          alt="Auto shop" 
          className="w-full h-full object-cover object-center"
        />
        {/* Lighter gradient overlays - just blend edges */}
        <div className="absolute inset-0 bg-gradient-to-l from-transparent via-slate-950/30 to-slate-950" />
        <div className="absolute inset-0 bg-gradient-to-b from-slate-950/20 via-transparent to-slate-950/60" />
        <div className="absolute inset-0 bg-slate-950/20" />
      </div>

      {/* Background decoration */}
      <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-20">
         <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] bg-brand-blue/10 rounded-full blur-[100px]" />
         <div className="absolute bottom-[-10%] left-[-10%] w-[600px] h-[600px] bg-brand-orange/10 rounded-full blur-[120px]" />
         {/* Grid lines */}
         <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20"></div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="lg:grid lg:grid-cols-12 lg:gap-8 items-center">
          
          {/* Text Content */}
          <div className="sm:text-center md:max-w-2xl md:mx-auto lg:col-span-6 lg:text-left mb-12 lg:mb-0">
            <h1 className="text-4xl tracking-tight font-extrabold text-white sm:text-5xl md:text-6xl lg:text-5xl xl:text-6xl mb-6">
              AI-Powered<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-blue to-brand-accent">
                Expert Diagnosis
              </span>
            </h1>
            <p className="mt-3 text-base text-slate-200 sm:mt-5 sm:text-lg sm:max-w-xl sm:mx-auto md:mt-5 md:text-xl lg:mx-0 drop-shadow-[0_2px_4px_rgba(0,0,0,0.8)]">
              Like having a 30-year master tech in your pocket. Get expert diagnostic guidance, not just specs.
            </p>
            <p className="mt-4 text-base text-slate-300 sm:text-lg sm:max-w-xl sm:mx-auto lg:mx-0 drop-shadow-[0_2px_4px_rgba(0,0,0,0.8)]">
              Stop guessing. Start diagnosing. AI-powered expertise that thinks through problems with you.
            </p>
            <div className="mt-8 sm:max-w-lg sm:mx-auto sm:text-center lg:text-left lg:mx-0">
              <a
                href="/auth"
                className="inline-flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-full text-white bg-brand-blue hover:bg-cyan-600 transition-all shadow-lg hover:shadow-brand-blue/25 md:text-lg md:px-10"
              >
                <Icons.Zap className="w-5 h-5 mr-2" />
                Start Diagnosis
              </a>
              <p className="mt-4 text-sm text-slate-300 drop-shadow-[0_2px_4px_rgba(0,0,0,0.8)]">
                Trusted by professional technicians nationwide.
              </p>
            </div>
          </div>

          {/* Chat Interface Demo */}
          <div className="lg:col-span-6 relative">
            <div className="relative rounded-2xl bg-slate-900/95 border border-slate-800 shadow-2xl overflow-hidden animate-fade-in-up flex flex-col backdrop-blur-sm">
              {/* Fake Browser Header */}
              <div className="bg-slate-900 px-4 py-3 border-b border-slate-800 flex items-center space-x-2 shrink-0">
                <div className="flex space-x-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
                </div>
                <div className="ml-4 bg-slate-950 rounded-md px-3 py-1 text-xs text-slate-500 flex-1 font-mono text-center border border-slate-800">
                  automotive.aurora-sentient.net
                </div>
              </div>

              {/* Chat Area */}
              <div 
                className="p-6 min-h-[400px] flex flex-col font-mono text-sm relative bg-slate-950/50"
              >
                
                {/* User Message */}
                <div className="flex justify-end mb-6 shrink-0">
                  <div className="bg-slate-800 text-white border border-slate-700 rounded-2xl rounded-tr-sm py-3 px-4 max-w-[85%] shadow-md">
                    <p>{typedText}<span className="animate-pulse">|</span></p>
                  </div>
                </div>

                {/* AI Response */}
                {showResponse && (
                  <div className="flex justify-start animate-fade-in-up">
                    <div className="bg-slate-900/80 border border-slate-800 text-slate-200 rounded-2xl rounded-tl-sm py-4 px-5 max-w-[95%] shadow-md">
                      <div className="flex items-center space-x-2 mb-3">
                        <Icons.Cpu className="w-4 h-4 text-brand-blue" />
                        <span className="text-xs font-bold text-brand-blue uppercase">Autotech AI</span>
                        <span className="text-[10px] text-slate-500 ml-2">Today at 7:47 AM</span>
                      </div>
                      
                      <div className="space-y-4 text-xs sm:text-sm leading-relaxed">
                        <div>
                            <h4 className="font-bold text-white mb-1 text-[11px] sm:text-xs tracking-wider">DIAGNOSIS:</h4>
                            <p className="text-slate-300">P0300 is a random/multiple cylinder misfire. On the 2015 Malibu 2.5L, here's how I'd approach it:</p>
                        </div>

                        <div>
                            <h4 className="font-bold text-white mb-1 text-[11px] sm:text-xs tracking-wider">CHECK FIRST:</h4>
                            <ol className="list-decimal list-outside ml-4 text-slate-300 space-y-1 marker:text-slate-500">
                                <li><span className="font-semibold text-white">Spark plugs</span> — These are known to foul early on this engine. Check gap (0.028") and condition.</li>
                                <li><span className="font-semibold text-white">Ignition coils</span> — Swap coils between cylinders and see if the misfire follows.</li>
                                <li><span className="font-semibold text-white">Fuel injectors</span> — Listen for clicking with a stethoscope. Check resistance (11-18Ω).</li>
                            </ol>
                        </div>

                        <div>
                            <h4 className="font-bold text-white mb-1 text-[11px] sm:text-xs tracking-wider">COMMON CAUSE:</h4>
                            <p className="text-slate-300">On this generation Malibu, the <span className="font-semibold text-brand-accent">PCV valve diaphragm</span> in the valve cover commonly fails, causing lean misfires. Worth inspecting.</p>
                        </div>

                        <div>
                            <h4 className="font-bold text-white mb-1 text-[11px] sm:text-xs tracking-wider">NEXT STEP:</h4>
                            <p className="text-slate-300">Which cylinder(s) are misfiring? Run live data and I'll help narrow it down.</p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

               {/* Input Area Simulation */}
               <div className="p-4 bg-slate-900 border-t border-slate-800">
                  <div className="flex items-center bg-slate-950 rounded-lg border border-slate-700 px-4 py-3">
                    <Icons.Wrench className="w-4 h-4 text-slate-500 mr-3" />
                    <span className="text-slate-500 text-sm">Ask about any vehicle...</span>
                  </div>
                </div>
            </div>
            
            {/* Floating badge - repositioned */}
            <div className="absolute -bottom-4 right-4 bg-slate-900/95 backdrop-blur border border-slate-800 px-4 py-3 rounded-xl shadow-xl hidden lg:flex items-center space-x-3">
              <div className="p-2 bg-brand-blue/10 rounded-lg">
                <Icons.CheckCircle2 className="w-5 h-5 text-brand-blue" />
              </div>
              <div>
                <p className="text-xs text-slate-400">The expertise you need</p>
                <p className="text-sm font-bold text-white">When you need it</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};