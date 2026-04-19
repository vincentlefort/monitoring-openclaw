module.exports = async (req, res) => {
  if (req.method !== 'POST') {
    return res.status(405).send('Method Not Allowed')
  }

  const chunks = []
  for await (const chunk of req) chunks.push(chunk)
  const body = Buffer.concat(chunks).toString()
  const params = new URLSearchParams(body)
  const password = params.get('password') || ''

  const expected = process.env.DASHBOARD_PASSWORD || ''

  if (expected && password === expected) {
    const token = Buffer.from(password + ':openclaw').toString('base64')
    res.setHeader('Set-Cookie',
      `openclaw_auth=${token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=604800`
    )
    res.setHeader('Location', '/')
    return res.status(302).end()
  }

  res.setHeader('Location', '/login?error=1')
  return res.status(302).end()
}
