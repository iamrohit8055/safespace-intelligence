import React from 'react'
import { Link } from 'react-router-dom'
import {
  MapPin,
  ArrowRight,
  ShieldCheck,
  Compass,
  FileCheck2,
  Wrench,
  Layers,
  ChevronRight,
  Building2,
  Eye,
} from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { MapComponent } from '../../components/common/MapComponent'
import heroImage from '../../assets/hero.jpg'

export const LandingPage: React.FC = () => {
  return (
    <div className="space-y-16 sm:space-y-24 py-6 sm:py-10 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto antialiased">
      {/* 1. Asymmetric Editorial Hero */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center pt-2 sm:pt-6">
        <div className="lg:col-span-6 space-y-6">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-xs bg-[#DCE5D9]/50 dark:bg-[#18372C]/40 border border-[#829783]/30 text-[10px] font-mono uppercase tracking-widest text-[#18372C] dark:text-[#DCE5D9]">
            <Compass className="h-3 w-3 text-[#C36B48]" />
            <span>Civic Infrastructure Intelligence</span>
          </div>

          <h1 className="font-serif-headline text-3xl sm:text-4xl md:text-5xl font-normal leading-[1.12] text-[#18372C] dark:text-[#F5F2EA]">
            Better streets begin with better information.
          </h1>

          <p className="text-sm sm:text-base text-[#73766F] dark:text-[#829783] leading-relaxed max-w-xl font-sans">
            Document infrastructure deficiencies. Make public conditions visible. Help municipal teams understand where inspections and repairs matter most across our built environment.
          </p>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Link to="/citizen/submit">
              <Button size="md" variant="primary" className="h-10 px-4 text-xs font-medium">
                Report an Infrastructure Defect <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
              </Button>
            </Link>
            <Link to="/map">
              <Button variant="outline" size="md" className="h-10 px-4 text-xs font-medium">
                <MapPin className="h-3.5 w-3.5 mr-1.5 text-[#C36B48]" />
                Explore Infrastructure Map
              </Button>
            </Link>
          </div>

          <div className="pt-4 border-t border-[#829783]/20 flex items-center gap-6 text-[11px] font-mono text-[#73766F] dark:text-[#829783]">
            <div>
              <span className="text-[#18372C] dark:text-[#F5F2EA] font-semibold block text-base font-mono-numbers">05</span>
              <span>Deficiency Taxonomies</span>
            </div>
            <div className="h-6 w-px bg-[#829783]/30" />
            <div>
              <span className="text-[#18372C] dark:text-[#F5F2EA] font-semibold block text-base font-mono-numbers">~100m</span>
              <span>Privacy Coordinate Fuzzing</span>
            </div>
            <div className="h-6 w-px bg-[#829783]/30" />
            <div>
              <span className="text-[#18372C] dark:text-[#F5F2EA] font-semibold block text-base font-mono-numbers">SHA-256</span>
              <span>Photographic Verification</span>
            </div>
          </div>
        </div>

        {/* Hero Photographic Composition */}
        <div className="lg:col-span-6 relative">
          <div className="relative rounded-sm overflow-hidden border border-[#829783]/30 dark:border-[#829783]/20 shadow-[0_4px_20px_rgba(24,55,44,0.08)] bg-[#FFFEFA] dark:bg-[#1E211E]">
            <img
              src={heroImage}
              alt="Bengaluru metropolitan boulevard showing tree canopy and pedestrian sidewalk"
              className="w-full h-[380px] sm:h-[460px] object-cover"
              loading="eager"
            />
            {/* Editorial Image Overlay Caption */}
            <div className="p-3 bg-[#FFFEFA]/95 dark:bg-[#1E211E]/95 border-t border-[#829783]/20 flex flex-col sm:flex-row sm:items-center justify-between text-[11px] gap-2">
              <div className="flex items-center gap-1.5 text-[#18372C] dark:text-[#F5F2EA] font-mono">
                <Building2 className="h-3.5 w-3.5 text-[#C36B48]" />
                <span className="font-medium">Shantala Nagar Ward, MG Road Corridor</span>
              </div>
              <span className="text-[10px] font-mono text-[#73766F] dark:text-[#829783]">
                12.9716° N, 77.5946° E &bull; BBMP Central
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Civic Intelligence & Methodology Note */}
      <section className="rounded-sm border-l-2 border-[#C36B48] border-y border-r border-[#829783]/25 bg-[#FFFEFA] dark:bg-[#1E211E] p-4 sm:p-5 shadow-2xs">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#C36B48] font-semibold block">
              Methodology &amp; Civic Ethics Invariant
            </span>
            <p className="text-xs text-[#292D29] dark:text-[#F5F2EA] leading-relaxed max-w-3xl">
              The <strong>Safety Deficiency Index (SDI)</strong> quantifies verifiable physical infrastructure defects (broken illumination, sidewalk obstruction, pedestrian hazards, unmaintained transit points). It is mathematically decoupled from crime statistics and must <strong>never</strong> be interpreted as a measure of crime probability or personal danger.
            </p>
          </div>
          <Link to="/map" className="shrink-0 text-xs font-mono font-medium text-[#244B3B] dark:text-[#DCE5D9] hover:underline flex items-center gap-1">
            Read Spatial Methodology <ChevronRight className="h-3 w-3" />
          </Link>
        </div>
      </section>

      {/* 3. The Architecture of Defect Intelligence (Not 3 generic cards) */}
      <section className="space-y-8">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between border-b border-[#829783]/20 pb-4 gap-2">
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#73766F] dark:text-[#829783] block">
              Core Principles
            </span>
            <h2 className="font-serif-headline text-2xl sm:text-3xl font-normal text-[#18372C] dark:text-[#F5F2EA] mt-1">
              How SafeSpace Measures the Built Environment
            </h2>
          </div>
          <span className="text-xs text-[#73766F] font-mono">
            Versioned &bull; Reproducible &bull; Deterministic
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="border-t border-[#829783]/30 pt-4 space-y-2">
            <span className="text-[11px] font-mono text-[#C36B48] block">01 / CAPTURE</span>
            <h3 className="text-sm font-semibold text-[#18372C] dark:text-[#F5F2EA]">
              Objective Ground Observations
            </h3>
            <p className="text-xs text-[#73766F] dark:text-[#829783] leading-relaxed">
              Citizens record physical anomalies: dead lamps, fractured paving slabs, open drain pits, or blocked walkways. Every upload is stripped of metadata to protect identity.
            </p>
          </div>

          <div className="border-t border-[#829783]/30 pt-4 space-y-2">
            <span className="text-[11px] font-mono text-[#C36B48] block">02 / VERIFY</span>
            <h3 className="text-sm font-semibold text-[#18372C] dark:text-[#F5F2EA]">
              Independent Moderation
            </h3>
            <p className="text-xs text-[#73766F] dark:text-[#829783] leading-relaxed">
              Municipal verifiers inspect photographic evidence, eliminate spatial duplicates using spatio-temporal radius algorithms, and assign standardized 1–5 severity ratings.
            </p>
          </div>

          <div className="border-t border-[#829783]/30 pt-4 space-y-2">
            <span className="text-[11px] font-mono text-[#C36B48] block">03 / QUANTIFY</span>
            <h3 className="text-sm font-semibold text-[#18372C] dark:text-[#F5F2EA]">
              Spatial Deficit Scoring
            </h3>
            <p className="text-xs text-[#73766F] dark:text-[#829783] leading-relaxed">
              PostGIS polygon engines aggregate verified defects into bounded wards, computing weighted Safety Deficiency Index (SDI) values alongside statistical confidence indices.
            </p>
          </div>

          <div className="border-t border-[#829783]/30 pt-4 space-y-2">
            <span className="text-[11px] font-mono text-[#C36B48] block">04 / REMEDIATE</span>
            <h3 className="text-sm font-semibold text-[#18372C] dark:text-[#F5F2EA]">
              Field Work Orders
            </h3>
            <p className="text-xs text-[#73766F] dark:text-[#829783] leading-relaxed">
              Remediation tasks dispatch directly to departmental engineering crews with location coordinates, completion audit trails, and resolved defect photographic logs.
            </p>
          </div>
        </div>
      </section>

      {/* 4. Geographic Intelligence & Interactive Map Preview */}
      <section className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-2 border-b border-[#829783]/20 pb-3">
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-[#73766F] dark:text-[#829783] block">
              Cartographic Exploration
            </span>
            <h2 className="font-serif-headline text-2xl sm:text-3xl font-normal text-[#18372C] dark:text-[#F5F2EA] mt-1">
              Live Infrastructure Defect Surveillance
            </h2>
          </div>
          <Link to="/map">
            <Button variant="outline" size="xs" className="font-mono text-xs">
              Open Full Cartographic Canvas <ArrowRight className="h-3 w-3 ml-1" />
            </Button>
          </Link>
        </div>

        <div className="rounded-sm overflow-hidden border border-[#829783]/30 dark:border-[#829783]/20 bg-[#FFFEFA] dark:bg-[#1E211E]">
          <MapComponent
            height="420px"
            center={[77.5946, 12.9716]}
            zoom={13}
          />
        </div>
        <div className="flex flex-wrap items-center justify-between text-[11px] font-mono text-[#73766F] px-1">
          <span>PostGIS EPSG:4326 Coordinate Reference System</span>
          <span>OpenStreetMap &bull; Esri Cartography &bull; Humanitarian OSM</span>
        </div>
      </section>

      {/* 5. Report-to-Verification-to-Repair Workflow Banner */}
      <section className="rounded-sm border border-[#829783]/30 bg-[#FAF8F4] dark:bg-[#1E211E] p-6 sm:p-8 space-y-6">
        <div className="max-w-2xl space-y-2">
          <span className="text-[10px] font-mono uppercase tracking-widest text-[#C36B48] font-semibold block">
            Accountability Lifecycle
          </span>
          <h2 className="font-serif-headline text-2xl sm:text-3xl font-normal text-[#18372C] dark:text-[#F5F2EA]">
            Every observation logged is tracked to completion.
          </h2>
          <p className="text-xs sm:text-sm text-[#73766F] dark:text-[#829783] leading-relaxed">
            SafeSpace provides end-to-end transparency. Citizens observe status updates in real time as municipal engineers review reports, schedule work crews, and complete repairs.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-[#829783]/20">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Eye className="h-4 w-4 text-[#244B3B] dark:text-[#DCE5D9]" />
              <span className="text-xs font-semibold text-[#18372C] dark:text-[#F5F2EA]">1. Observation Submitted</span>
            </div>
            <p className="text-[11px] text-[#73766F] dark:text-[#829783] leading-relaxed">
              Photographed by local residents with coordinate fuzzed to protect residential privacy.
            </p>
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <FileCheck2 className="h-4 w-4 text-[#C5A66B]" />
              <span className="text-xs font-semibold text-[#18372C] dark:text-[#F5F2EA]">2. Severity Verification</span>
            </div>
            <p className="text-[11px] text-[#73766F] dark:text-[#829783] leading-relaxed">
              Evaluated on a 1–5 scale by certified verifiers and cross-checked against duplicate candidates.
            </p>
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Wrench className="h-4 w-4 text-[#C36B48]" />
              <span className="text-xs font-semibold text-[#18372C] dark:text-[#F5F2EA]">3. Engineering Resolution</span>
            </div>
            <p className="text-[11px] text-[#73766F] dark:text-[#829783] leading-relaxed">
              Assigned as a municipal work order and tracked until physical restoration is confirmed.
            </p>
          </div>
        </div>
      </section>

      {/* 6. Closing Call to Action */}
      <section className="text-center py-10 sm:py-14 px-4 bg-[#244B3B] dark:bg-[#18372C] text-[#FFFEFA] rounded-sm space-y-4">
        <span className="text-[10px] font-mono uppercase tracking-widest text-[#DCE5D9] block">
          Civic Partnership
        </span>
        <h2 className="font-serif-headline text-2xl sm:text-3xl md:text-4xl font-normal leading-tight max-w-xl mx-auto">
          Help build safer, well-lit, accessible streets.
        </h2>
        <p className="text-xs sm:text-sm text-[#DCE5D9]/80 max-w-md mx-auto leading-relaxed">
          Join thousands of citizens, verifiers, and civic engineers documenting public infrastructure conditions in Bengaluru.
        </p>
        <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
          <Link to="/citizen/submit">
            <Button size="md" className="bg-[#FFFEFA] text-[#18372C] hover:bg-[#F5F2EA] px-5 py-2 font-medium text-xs">
              Submit an Infrastructure Observation
            </Button>
          </Link>
          <Link to="/login">
            <Button variant="outline" size="md" className="border-[#DCE5D9]/50 text-[#FFFEFA] hover:bg-[#18372C]/40 px-5 py-2 text-xs">
              Sign In to Workbench
            </Button>
          </Link>
        </div>
      </section>
    </div>
  )
}
