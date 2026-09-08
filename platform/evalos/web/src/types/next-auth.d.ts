import 'next-auth'
import 'next-auth/jwt'

declare module 'next-auth' {
  interface Session {
    user: {
      userId: string
      email: string
      name: string
      image?: string | null
      roles: string[]
      isAdmin: boolean
    }
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    userId: string
    roles: string[]
    accessToken?: string
    idToken?: string
    refreshToken?: string
    expiresAt?: number
  }
}
