import api from './index'
import type { ClusterInfoApi } from '../types/cluster'

export const clusterApi = {
  getCluster: (): Promise<{ data: ClusterInfoApi }> =>
    api.get<ClusterInfoApi>('/cluster').then((res) => ({ data: res.data })),
}

export default clusterApi
