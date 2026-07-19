export type DocumentStatus = 'pending' | 'processing' | 'done' | 'error'

export interface DocumentSummary {
  id: string
  original_filename: string
  mime_type: string
  file_size: number
  status: DocumentStatus
  progress_percent: number
  document_type: string | null
  document_number: string | null
  detected_language: string | null
  created_at: string
  processing_started_at: string | null
  estimated_completion_at: string | null
}

export interface DocumentDetail extends DocumentSummary {
  error_message: string | null
  ocr_text: string | null
  ocr_confidence: number | null
  issuing_authority: string | null
  issue_date: string | null
  expiry_date: string | null
  key_fields: Record<string, string> | null
  summary_original: string | null
  summary_english: string | null
  updated_at: string
}

export interface AuthUser {
  id: string
  email: string
  full_name: string
  is_admin: boolean
}

export interface AdminUserSummary {
  id: string
  email: string
  full_name: string
  is_admin: boolean
  created_at: string
  document_count: number
  done_count: number
  error_count: number
}
