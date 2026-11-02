import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import React from 'react'
import { LandingPage } from '../pages/public/LandingPage'

describe('Urban Editorial Landing Page', () => {
  it('renders editorial headline and supporting copy correctly', () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    )

    expect(
      screen.getByText(/Better streets begin with better information\./i)
    ).toBeInTheDocument()

    expect(
      screen.getByText(/Document infrastructure deficiencies\. Make public conditions visible\./i)
    ).toBeInTheDocument()
  })

  it('renders primary and secondary call-to-action actions', () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    )

    expect(
      screen.getByRole('button', { name: /Report an Infrastructure Defect/i })
    ).toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: /Explore Infrastructure Map/i })
    ).toBeInTheDocument()
  })

  it('renders the civic ethics and SDI methodology statement', () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    )

    expect(
      screen.getByText(/Methodology & Civic Ethics Invariant/i)
    ).toBeInTheDocument()

    expect(
      screen.getByText(/quantifies verifiable physical infrastructure defects/i)
    ).toBeInTheDocument()
  })

  it('renders the 4-stage architecture of defect intelligence workflow', () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    )

    expect(screen.getByText(/01 \/ CAPTURE/i)).toBeInTheDocument()
    expect(screen.getByText(/02 \/ VERIFY/i)).toBeInTheDocument()
    expect(screen.getByText(/03 \/ QUANTIFY/i)).toBeInTheDocument()
    expect(screen.getByText(/04 \/ REMEDIATE/i)).toBeInTheDocument()
  })

  it('renders the Bengaluru metropolitan context caption for the hero photograph', () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    )

    expect(
      screen.getByText(/Shantala Nagar Ward, MG Road Corridor/i)
    ).toBeInTheDocument()

    expect(
      screen.getByText(/12\.9716° N, 77\.5946° E • BBMP Central/i)
    ).toBeInTheDocument()
  })
})
