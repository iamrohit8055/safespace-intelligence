import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  UploadCloud,
  CheckCircle2,
  MapPin,
  AlertCircle,
  FileImage,
  X,
  Camera,
} from 'lucide-react'
import { reportsApi } from '../../api/reports.api'
import { useUIStore } from '../../stores/ui.store'
import { MapComponent } from '../../components/common/MapComponent'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/Textarea'
import { Select } from '../../components/ui/Select'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../components/ui/Card'

export const SubmitReportPage: React.FC = () => {
  const navigate = useNavigate()
  const { addToast } = useUIStore()

  // Form State
  const [title, setTitle] = useState('')
  const [categoryId, setCategoryId] = useState<number | ''>('')
  const [description, setDescription] = useState('')
  const [addressText, setAddressText] = useState('')
  const [observedAt, setObservedAt] = useState(() => {
    const now = new Date()
    return now.toISOString().slice(0, 16)
  })
  const [coordinates, setCoordinates] = useState<{ latitude: number; longitude: number }>({
    latitude: 12.9716,
    longitude: 77.5946,
  })

  // Media State
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)

  // Status State
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Fetch active categories
  const { data: categories = [], isLoading: isLoadingCategories } = useQuery({
    queryKey: ['report-categories'],
    queryFn: reportsApi.getCategories,
  })

  // Set default category when loaded
  React.useEffect(() => {
    if (categories.length > 0 && categoryId === '') {
      setCategoryId(categories[0].id)
    }
  }, [categories, categoryId])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFileError(null)
    const file = e.target.files?.[0]
    if (!file) return

    // Validate MIME
    const allowed = ['image/jpeg', 'image/png', 'image/webp']
    if (!allowed.includes(file.type)) {
      setFileError('Invalid file type. Only JPEG, PNG, and WebP images are accepted.')
      return
    }

    // Validate size (15MB)
    const maxSizeBytes = 15 * 1024 * 1024
    if (file.size > maxSizeBytes) {
      setFileError('File exceeds maximum size limit of 15MB.')
      return
    }

    setSelectedFile(file)
    setPreviewUrl(URL.createObjectURL(file))
  }

  const removeSelectedFile = () => {
    setSelectedFile(null)
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
      setPreviewUrl(null)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMessage(null)

    if (!categoryId) {
      setErrorMessage('Please select a deficiency category.')
      return
    }

    setIsSubmitting(true)

    try {
      // 1. Create Report
      const report = await reportsApi.createReport({
        title,
        description,
        category_id: Number(categoryId),
        latitude: coordinates.latitude,
        longitude: coordinates.longitude,
        address_text: addressText || undefined,
        observed_at: new Date(observedAt).toISOString(),
      })

      // 2. Upload Media if attached
      if (selectedFile) {
        try {
          await reportsApi.uploadMedia(report.id, selectedFile)
        } catch (mediaErr: any) {
          console.warn('Media upload warning:', mediaErr)
          addToast({
            type: 'warning',
            title: 'Report Created, Photo Pending',
            message: 'Report submitted, but photo processing encountered a delay.',
          })
        }
      }

      addToast({
        type: 'success',
        title: 'Report Submitted Successfully',
        message: 'Your report is now in the municipal verification queue.',
      })

      navigate(`/citizen/reports/${report.id}`)
    } catch (err: any) {
      const detail =
        err.response?.data?.detail || 'Failed to submit report. Please check the form fields.'
      setErrorMessage(typeof detail === 'string' ? detail : JSON.stringify(detail))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="pb-3 border-b border-[#829783]/25 dark:border-[#829783]/20">
        <span className="text-[10px] font-mono uppercase tracking-widest text-[#C36B48] font-semibold block">
          Public Space Observation
        </span>
        <h1 className="font-serif-headline text-xl sm:text-2xl font-normal tracking-tight text-[#18372C] dark:text-[#F5F2EA] mt-0.5">
          Document an Infrastructure Deficiency
        </h1>
        <p className="text-xs text-[#73766F] dark:text-[#829783] mt-0.5">
          Record street illumination failures, pathway damage, visibility obstructions, or public safety asset deficits.
        </p>
      </div>

      {errorMessage && (
        <div className="p-3 rounded-sm bg-[#FBF0EB] border border-[#C36B48]/40 text-[#A25335] text-xs flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Left Column: Defect Details */}
          <div className="space-y-4">
            <Card>
              <CardHeader className="py-2.5">
                <CardTitle className="text-xs uppercase tracking-wider text-slate-600 dark:text-slate-300">
                  Deficiency Information
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 pt-3">
                <Input
                  label="Title / Summary"
                  placeholder="e.g. Non-functioning street lamp on 100 Feet Road"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                />

                <Select
                  label="Category Taxonomy"
                  value={categoryId}
                  onChange={(e) => setCategoryId(Number(e.target.value))}
                  required
                >
                  {categories.map((cat) => (
                    <option key={cat.id} value={cat.id}>
                      {cat.name} ({cat.code})
                    </option>
                  ))}
                </Select>

                <Textarea
                  label="Detailed Description"
                  placeholder="Describe the physical condition, specific hazards, and landmarks..."
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  required
                />

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <Input
                    label="Observed Date & Time"
                    type="datetime-local"
                    value={observedAt}
                    onChange={(e) => setObservedAt(e.target.value)}
                    required
                  />

                  <Input
                    label="Street / Landmark (Optional)"
                    placeholder="Near Cubbon Park Metro Gate, MG Road, Bengaluru"
                    value={addressText}
                    onChange={(e) => setAddressText(e.target.value)}
                  />
                </div>
              </CardContent>
            </Card>

            {/* Photographic Evidence Card */}
            <Card>
              <CardHeader className="py-2.5">
                <CardTitle className="text-xs uppercase tracking-wider text-slate-600 dark:text-slate-300">
                  Photographic Evidence
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2.5 pt-3">
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Upload an image of the physical defect (JPEG, PNG, WebP up to 15MB). EXIF metadata and GPS are automatically stripped on upload for citizen privacy.
                </p>

                {previewUrl ? (
                  <div className="relative rounded-md overflow-hidden border border-slate-200 dark:border-slate-800 bg-slate-100 dark:bg-slate-900 p-1.5">
                    <img
                      src={previewUrl}
                      alt="Defect preview"
                      className="w-full h-44 object-cover rounded-xs"
                    />
                    <button
                      type="button"
                      onClick={removeSelectedFile}
                      className="absolute top-3 right-3 p-1 rounded-full bg-slate-950/80 text-white hover:bg-rose-600 transition-colors cursor-pointer"
                      aria-label="Remove photo"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                    <div className="mt-1 px-1 flex items-center justify-between text-[10px] font-mono text-slate-500">
                      <span className="truncate max-w-[200px]">{selectedFile?.name}</span>
                      <span>{((selectedFile?.size || 0) / (1024 * 1024)).toFixed(2)} MB</span>
                    </div>
                  </div>
                ) : (
                  <label className="border-2 border-dashed border-[#829783]/40 hover:border-[#244B3B] dark:hover:border-[#DCE5D9] rounded-sm p-5 flex flex-col items-center justify-center cursor-pointer transition-colors bg-[#FAF8F4] dark:bg-[#1E211E]/40">
                    <Camera className="h-6 w-6 text-[#829783] mb-1.5" />
                    <span className="text-xs font-medium text-[#18372C] dark:text-[#F5F2EA]">
                      Click to attach defect photo
                    </span>
                    <span className="text-[10px] text-[#73766F] mt-0.5 font-mono">
                      JPEG, PNG, WebP &bull; Max 15MB (EXIF stripped)
                    </span>
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handleFileChange}
                      className="hidden"
                    />
                  </label>
                )}

                {fileError && (
                  <p className="text-xs text-[#C36B48] font-medium">{fileError}</p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right Column: Spatial Coordinates & Map Picker */}
          <div className="space-y-4">
            <Card className="h-full flex flex-col">
              <CardHeader className="py-2.5">
                <CardTitle className="text-xs uppercase tracking-wider text-[#73766F] dark:text-[#829783]">
                  Deficiency Location Map
                </CardTitle>
                <CardDescription>
                  Click on the map to pin the exact physical deficiency location.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 pt-3 flex-1 flex flex-col">
                <div className="flex-1 min-h-[300px] rounded-sm overflow-hidden border border-[#829783]/30 dark:border-[#829783]/20 relative">
                  <MapComponent
                    interactivePick={true}
                    selectedCoordinates={coordinates}
                    onLocationPick={(coords) => setCoordinates(coords)}
                    center={[coordinates.longitude, coordinates.latitude]}
                    zoom={13}
                    height="100%"
                  />
                </div>

                <div className="p-2.5 rounded-sm bg-[#FAF8F4] dark:bg-[#18372C]/20 border border-[#829783]/30 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1.5 text-[#73766F]">
                    <MapPin className="h-3.5 w-3.5 text-[#C36B48]" />
                    <span>Coordinates:</span>
                  </div>
                  <div className="font-mono text-[#18372C] dark:text-[#F5F2EA] text-[11px]">
                    {coordinates.latitude.toFixed(5)}° N, {coordinates.longitude.toFixed(5)}° E
                  </div>
                </div>

                <div className="pt-2">
                  <Button
                    type="submit"
                    variant="primary"
                    className="w-full"
                    size="md"
                    isLoading={isSubmitting}
                  >
                    Submit Infrastructure Report
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </form>
    </div>
  )
}
