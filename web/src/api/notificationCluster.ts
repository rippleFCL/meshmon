import api from './index'
import type { NotificationClusterApi } from '../types/notificationCluster'

export const notificationApi = {
  getCluster: (): Promise<{ data: NotificationClusterApi }> =>
    api.get<NotificationClusterApi>('/notification_cluster').then((res) => ({ data: res.data })),
}

export default notificationApi
