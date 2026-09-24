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
        token.userId       = (profile as Record<string, unknown>)?.['sub'] as string ?? token.sub
        token.roles        = ((profile as Record<string, unknown>)?.['realm_access'] as { roles?: string[] })?.roles ?? []
        // HC-4: extract tenant_id from Keycloak custom claim
        token.tenant_id    = (profile as Record<string, unknown>)?.['tenant_id'] as string ?? null
      }
      return token
    },
    async session({ session, token }) {
      (session.user as Record<string, unknown>)['userId']      = token.userId as string
      (session.user as Record<string, unknown>)['roles']       = token.roles as string[]
      (session.user as Record<string, unknown>)['accessToken'] = token.accessToken as string
      // HC-4: propagate tenant_id into session
      (session.user as Record<string, unknown>)['tenant_id']   = token.tenant_id as string | null
      return session
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
}

export default NextAuth(authOptions)
