import React from 'react';
import { Icons } from './Icons';

export const Footer: React.FC = () => {
  return (
    <footer className="bg-slate-950 border-t border-slate-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="md:flex md:items-center md:justify-between">
          <div className="flex justify-center md:justify-start">
            <div className="flex items-center space-x-2">
               <Icons.Wrench className="h-5 w-5 text-slate-600" />
               <span className="text-lg font-bold text-slate-500">
                 Autotech AI
               </span>
            </div>
          </div>
          <div className="mt-8 md:mt-0">
            <p className="text-center text-sm text-slate-600">
              &copy; {new Date().getFullYear()} Aurora Sentient. All rights reserved.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
};