import NextAuth, { NextAuthOptions } from 'next-auth'
import KeycloakProvider from 'next-auth/providers/keycloak'

export const authOptions: NextAuthOptions = {
  providers: [
    KeycloakProvider({
      clientId:     process.env.KEYCLOAK_CLIENT_ID!,
      clientSecret: process.env.KEYCLOAK_CLIENT_SECRET!,
      issuer:       process.env.KEYCLOAK_ISSUER!,
    }),
  ],
  callbacks: {
    async jwt({ token, account, profile }) {
      if (account) {
        token.accessToken  = account.access_token
        token.refreshToken = account.refresh_token
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        token.userId       = (profile as any)?.sub ?? token.sub
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        token.roles        = (profile as any)?.realm_access?.roles ?? []
        // HC-4: extract tenant_id from Keycloak custom claim
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        token.tenant_id    = (profile as any)?.tenant_id ?? null
      }
      return token
    },
    async session({ session, token }) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ;(session.user as any).userId      = token.userId as string
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ;(session.user as any).roles       = token.roles as string[]
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ;(session.user as any).accessToken = token.accessToken as string
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ;(session.user as any).tenant_id   = token.tenant_id as string | null
      return session
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
}

export default NextAuth(authOptions)
