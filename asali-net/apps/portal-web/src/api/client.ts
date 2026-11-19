// A thin fetch wrapper. Errors arrive as problem JSON (RFC 9457) and stay that way, so a screen can show the sentence.

export interface Problem {
  type: string
  title: string
  status: number
  detail: string
  code: string
}

export class ApiError extends Error {
  readonly problem: Problem
  constructor(problem: Problem) {
    super(problem.detail || problem.title)
    this.problem = problem
  }
}

function asProblem(status: number, body: unknown): Problem {
  if (body && typeof body === 'object' && 'code' in body && 'title' in body) return body as Problem
  return {
    type: 'about:blank',
    title: 'Something went wrong',
    status,
    detail: 'The server sent a reply we could not read. Try again in a moment.',
    code: 'bad_reply',
  }
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init
  let response: Response
  try {
    response = await fetch(path, {
      credentials: 'same-origin',
      ...rest,
      headers: { ...(json !== undefined ? { 'content-type': 'application/json' } : {}), ...headers },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    })
  } catch {
    throw new ApiError({
      type: 'about:blank',
      title: 'No connection',
      status: 0,
      detail: 'This computer could not reach the server. Check the network and try again.',
      code: 'offline',
    })
  }
  const text = await response.text()
  let body: unknown
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = null
  }
  if (!response.ok) throw new ApiError(asProblem(response.status, body))
  return body as T
}
