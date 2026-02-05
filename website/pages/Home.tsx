import React from 'react';
import { Hero } from '../components/Hero';
import { Features } from '../components/Features';
import { HowItWorks } from '../components/HowItWorks';

export const Home: React.FC = () => {
  return (
    <>
      <Hero />
      <Features />
      <HowItWorks />
    </>
  );
};
