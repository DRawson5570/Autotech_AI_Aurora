import React, { useState, useEffect } from 'react';
import { Icons } from './Icons';

export const Header: React.FC = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <nav 
      className={`fixed top-0 w-full z-50 transition-all duration-300 ${
        isScrolled || isMobileMenuOpen ? 'bg-slate-950/90 backdrop-blur-md border-b border-slate-800' : 'bg-transparent border-transparent'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-20">
          {/* Logo */}
          <a href="/" className="flex-shrink-0 flex items-center space-x-2">
            <div className="bg-gradient-to-br from-brand-blue to-brand-accent p-2 rounded-lg">
              <Icons.Wrench className="h-6 w-6 text-white" />
            </div>
            <span className="text-xl font-bold text-white tracking-tight">
              Autotech <span className="text-brand-accent">AI</span>
            </span>
          </a>
          
          {/* Live Badge */}
          <div className="hidden sm:inline-flex items-center px-3 py-1 rounded-full bg-slate-900/80 border border-slate-700 ml-4">
            <span className="flex h-2 w-2 rounded-full bg-brand-accent mr-2 animate-pulse"></span>
            <span className="text-xs font-semibold text-slate-300 uppercase tracking-wide">Live for Pro Shops</span>
          </div>

          {/* Desktop Menu */}
          <div className="hidden md:block">
            <div className="ml-10 flex items-baseline space-x-8">
              <a href="/examples/" className="text-slate-300 hover:text-white transition-colors px-3 py-2 rounded-md text-sm font-medium">Usage Examples</a>
              <a href="#features" className="text-slate-300 hover:text-white transition-colors px-3 py-2 rounded-md text-sm font-medium">Features</a>
              <a href="#how-it-works" className="text-slate-300 hover:text-white transition-colors px-3 py-2 rounded-md text-sm font-medium">How it Works</a>
              <a 
                href="/auth" 
                className="bg-brand-blue hover:bg-blue-600 text-white px-5 py-2.5 rounded-full text-sm font-semibold transition-all shadow-lg shadow-blue-500/20"
              >
                Chat with Expert
              </a>
            </div>
          </div>

          {/* Mobile menu button */}
          <div className="-mr-2 flex md:hidden">
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="inline-flex items-center justify-center p-2 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 focus:outline-none"
            >
              {isMobileMenuOpen ? <Icons.X className="h-6 w-6" /> : <Icons.Menu className="h-6 w-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu */}
      {isMobileMenuOpen && (
        <div className="md:hidden bg-slate-900 border-b border-slate-800">
          <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
            <a 
              href="/examples/" 
              className="text-slate-300 hover:text-white block px-3 py-2 rounded-md text-base font-medium"
              onClick={() => setIsMobileMenuOpen(false)}
            >
              Usage Examples
            </a>
            <a 
              href="#features" 
              className="text-slate-300 hover:text-white block px-3 py-2 rounded-md text-base font-medium"
              onClick={() => setIsMobileMenuOpen(false)}
            >
              Features
            </a>
            <a 
              href="#how-it-works" 
              className="text-slate-300 hover:text-white block px-3 py-2 rounded-md text-base font-medium"
              onClick={() => setIsMobileMenuOpen(false)}
            >
              How it Works
            </a>
            <a 
              href="/auth" 
              className="bg-brand-blue text-white block px-3 py-2 rounded-md text-base font-medium mt-4 mx-2 text-center"
              onClick={() => setIsMobileMenuOpen(false)}
            >
              Chat with Expert
            </a>
          </div>
        </div>
      )}
    </nav>
  );
};