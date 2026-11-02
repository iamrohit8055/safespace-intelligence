import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import React from 'react'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/Select'

describe('Reporting UI Components', () => {
  it('renders input with label and helper text', () => {
    render(
      <Input
        label="Defect Title"
        placeholder="Enter defect summary"
        helperText="Be specific about the physical hazard"
      />
    )

    expect(screen.getByText('Defect Title')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Enter defect summary')).toBeInTheDocument()
    expect(screen.getByText('Be specific about the physical hazard')).toBeInTheDocument()
  })

  it('renders select with options and handles selection', () => {
    const categories = [
      { value: 1, label: 'Lighting Deficiency' },
      { value: 2, label: 'Walkway Hazard' },
    ]

    render(<Select label="Category" options={categories} />)

    expect(screen.getByText('Lighting Deficiency')).toBeInTheDocument()
    expect(screen.getByText('Walkway Hazard')).toBeInTheDocument()
  })

  it('handles button clicks and disabled states', () => {
    let clicked = false
    const { rerender } = render(
      <Button onClick={() => { clicked = true }}>Submit Report</Button>
    )

    fireEvent.click(screen.getByText('Submit Report'))
    expect(clicked).toBe(true)

    rerender(<Button disabled>Submit Report</Button>)
    expect(screen.getByText('Submit Report')).toBeDisabled()
  })
})
