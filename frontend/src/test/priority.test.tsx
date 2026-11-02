import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import React from 'react'
import { Badge } from '../components/ui/Badge'
import { formatScore, getPriorityColor, getStatusColor } from '../lib/utils'

describe('Priority & Status Formatting Utilities', () => {
  it('formats deficiency scores correctly with 2 decimal places', () => {
    expect(formatScore(4.256)).toBe('4.26')
    expect(formatScore(0)).toBe('0.00')
    expect(formatScore(null)).toBe('N/A')
    expect(formatScore(undefined)).toBe('N/A')
  })

  it('provides distinct colors for inspection priority tiers', () => {
    const critical = getPriorityColor('CRITICAL')
    const high = getPriorityColor('HIGH')
    const low = getPriorityColor('LOW')

    expect(critical.text).toMatch(/red|rose/)
    expect(high.text).toContain('amber')
    expect(low.text).toMatch(/blue|sky/)
  })

  it('renders Priority Badge correctly', () => {
    render(<Badge variant="priority" priority="CRITICAL" />)
    expect(screen.getByText(/CRITICAL/i)).toBeInTheDocument()
  })

  it('renders Status Badge correctly', () => {
    render(<Badge variant="status" status="VERIFIED" />)
    expect(screen.getByText(/VERIFIED/i)).toBeInTheDocument()
  })
})
