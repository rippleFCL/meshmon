import api from './index'
import type { EventApi } from '../types/events'

export const eventsApi = {
  getEvents: (): Promise<{ data: EventApi }> =>
    api.get<EventApi>('/events').then((res) => ({ data: res.data })),
}

export default eventsApi
