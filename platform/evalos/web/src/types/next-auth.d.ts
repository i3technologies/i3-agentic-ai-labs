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
      tenant_id?: string | null   // HC-4: propagated from Keycloak claim
    }
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    userId: string
    roles: string[]
    tenant_id?: string | null     // HC-4: from Keycloak custom claim
    accessToken?: string
    idToken?: string
    refreshToken?: string
    expiresAt?: number
  }
}
