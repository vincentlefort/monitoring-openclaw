export const config = {
  matcher: ['/((?!login$|login\\.html$|api/).*)'],
}

export default function middleware(request) {
  const url = new URL(request.url)
  const pathname = url.pathname

  if (
    pathname === '/login' ||
    pathname === '/login.html' ||
    pathname.startsWith('/api/') ||
    pathname.startsWith('/_vercel/')
  ) {
    return
  }

  const cookieStr = request.headers.get('cookie') || ''
  let authToken = ''
  for (const part of cookieStr.split(';')) {
    const [k, ...v] = part.trim().split('=')
    if (k && k.trim() === 'openclaw_auth') {
      authToken = v.join('=').trim()
      break
    }
  }

  const pwd = process.env.DASHBOARD_PASSWORD || ''
  const expected = btoa(pwd + ':openclaw')

  if (!pwd || authToken !== expected) {
    return Response.redirect(new URL('/login', request.url), 302)
  }
}
