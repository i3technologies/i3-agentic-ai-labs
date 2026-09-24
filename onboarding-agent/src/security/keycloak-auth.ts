/**
 * Keycloak Auth Middleware
 * Validates Bearer tokens issued by the i3 Keycloak realm.
 * Realm: https://sso.i3technologies.co.ke/realms/i3
 *
 * On success, attaches req.user = { sub, email, roles, preferred_username }
 * to the Express request object.
 *
 * HC-7: DEV_BYPASS_AUTH is permanently removed. JWT validation is mandatory
 * in all environments. Use a real Keycloak token for local development
 * (see platform/docs/02-keycloak-sso-guide.html for a local dev realm setup).
 */

import { Request, Response, NextFunction } from "express";
import jwt from "jsonwebtoken";
import jwksRsa from "jwks-rsa";

const jwksClient = jwksRsa({
  jwksUri: process.env.KEYCLOAK_JWKS_URI ??
    "https://sso.i3technologies.co.ke/realms/i3/protocol/openid-connect/certs",
  cache: true,
  cacheMaxAge: 600_000, // 10 minutes
});

function getSigningKey(
  header: jwt.JwtHeader,
  callback: jwt.SigningKeyCallback
): void {
  jwksClient.getSigningKey(header.kid, (err, key) => {
    if (err) return callback(err);
    const signingKey = key?.getPublicKey();
    callback(null, signingKey);
  });
}

export interface AuthUser {
  sub: string;
  email: string;
  preferred_username: string;
  roles: string[];
}

declare module "express-serve-static-core" {
  interface Request {
    user?: AuthUser;
  }
}

export function requireAuth(
  req: Request,
  res: Response,
  next: NextFunction
): void {
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith("Bearer ")) {
    res.status(401).json({ error: "Missing or malformed Authorization header" });
    return;
  }

  const token = authHeader.slice(7);

  jwt.verify(
    token,
    getSigningKey,
    {
      issuer: process.env.KEYCLOAK_ISSUER ??
        "https://sso.i3technologies.co.ke/realms/i3",
      algorithms: ["RS256"],
    },
    (err, decoded) => {
      if (err) {
        res.status(401).json({ error: "Invalid or expired token", detail: err.message });
        return;
      }

      const payload = decoded as Record<string, unknown>;
      const realmRoles =
        (payload.realm_access as Record<string, string[]> | undefined)
          ?.roles ?? [];

      req.user = {
        sub: payload.sub as string,
        email: payload.email as string,
        preferred_username: payload.preferred_username as string,
        roles: realmRoles,
      };

      next();
    }
  );
}

/** Role-based access guard — place after requireAuth. */
export function requireRole(...allowed: string[]) {
  return (req: Request, res: Response, next: NextFunction): void => {
    const userRoles = req.user?.roles ?? [];
    const hasRole = allowed.some((r) => userRoles.includes(r));
    if (!hasRole) {
      res.status(403).json({
        error: "Forbidden",
        required: allowed,
        yours: userRoles,
      });
      return;
    }
    next();
  };
}
