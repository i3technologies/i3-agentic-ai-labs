import NextAuth, { type NextAuthOptions } from 'next-auth'
import KeycloakProvider from 'next-auth/providers/keycloak'

export const authOptions: NextAuthOptions = {
  providers: [
    KeycloakProvider({
      clientId: process.env.KEYCLOAK_CLIENT_ID!,
      clientSecret: '', // public client — no secret
      issuer: process.env.KEYCLOAK_ISSUER!,
      authorization: {
        params: {
          scope: 'openid email profile',
        },
      },
    }),
  ],

  callbacks: {
    async jwt({ token, account, profile }) {
      // On first sign-in, account and profile are populated
      if (account && profile) {
        token.accessToken = account.access_token
        token.idToken = account.id_token
        token.refreshToken = account.refresh_token
        token.expiresAt = account.expires_at

        // Extract realm roles from Keycloak JWT claims
        const p = profile as Record<string, unknown>
        const realmAccess = p['realm_access'] as
          | { roles?: string[] }
          | undefined
        token.roles = realmAccess?.roles ?? []
        token.userId = (p['sub'] as string) ?? token.sub ?? ''
        // HC-4: extract tenant_id from Keycloak custom claim
        token.tenant_id = (p['tenant_id'] as string) ?? null
      }
      return token
    },

    async session({ session, token }) {
      const roles = token.roles ?? []
      session.user = {
        ...session.user,
        userId: token.userId ?? '',
        email: token.email ?? session.user?.email ?? '',
        name: token.name ?? session.user?.name ?? '',
        roles,
        isAdmin: roles.includes('i3-admin'),
        // HC-4: propagate tenant_id into session
        tenant_id: (token.tenant_id as string | null) ?? null,
      }
      return session
    },
  },

  session: {
    strategy: 'jwt',
    maxAge: 8 * 60 * 60, // 8 hours
  },

  pages: {
    signIn: '/',
  },
}

export default NextAuth(authOptions)
