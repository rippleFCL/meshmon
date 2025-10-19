// Types reflecting the backend /api/events schema (OpenAPI)
// ApiEvent: { event_type: 'info'|'warning'|'error', message: string, title: string, date: string (ISO datetime) }
export type ApiEventType = 'info' | 'warning' | 'error'

export interface ApiEvent {
  event_type: ApiEventType
  message: string
  title: string
  date: string
}

export interface EventApi {
  events: ApiEvent[]
}
