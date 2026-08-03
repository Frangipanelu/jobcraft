export type RouteName = 'dashboard' | 'experience' | 'jd-analysis' | 'job' | 'prep' | 'review'

export interface RouteState {
  name: RouteName
  params: Record<string, string>
}

export function parseRoute(): RouteState {
  const hash = window.location.hash || '#/dashboard'
  const path = hash.replace(/^#\//, '').split('?')[0]
  const parts = path.split('/')

  const names: RouteName[] = ['dashboard', 'experience', 'jd-analysis', 'job', 'prep', 'review']
  const name = names.includes(parts[0] as RouteName) ? (parts[0] as RouteName) : 'dashboard'

  const params: Record<string, string> = {}
  if (name === 'prep' && parts[1]) params.submissionId = parts[1]
  if (name === 'review' && parts[1]) params.submissionId = parts[1]
  if (name === 'job' && parts[1]) params.jobId = parts[1]

  return { name, params }
}

export function navigate(name: RouteName, params?: Record<string, string>): void {
  let path = `#/${name}`
  if (name === 'prep' || name === 'review') {
    path += `/${params?.submissionId || ''}`
  }
  if (name === 'job') {
    path += `/${params?.jobId || ''}`
  }
  window.location.hash = path
}
