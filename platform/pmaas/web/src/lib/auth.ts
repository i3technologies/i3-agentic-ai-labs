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
        // @ts-expect-error keycloak sub
        token.userId       = profile?.sub ?? token.sub
        // @ts-expect-error keycloak roles
        token.roles        = profile?.realm_access?.roles ?? []
      }
      return token
    },
    async session({ session, token }) {
      // @ts-expect-error custom fields
      session.user.userId      = token.userId as string
      // @ts-expect-error custom fields
      session.user.roles       = token.roles as string[]
      // @ts-expect-error custom fields
      session.user.accessToken = token.accessToken as string
      return session
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
}

export default NextAuth(authOptions)
