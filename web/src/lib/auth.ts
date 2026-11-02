import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";

export const { handlers, auth } = NextAuth({
    providers: [GitHub],
    pages: {
        signIn: "/auth/login",
    },
    callbacks: {
        async jwt({ token, account }) {
            if (account?.provider === "github") {
                token.id = `github:${account.providerAccountId}`;
            }
            return token;
        },
        async session({ session, token }) {
            if (session.user && typeof token.id === "string") {
                session.user.id = token.id;
            }
            return session;
        },
    },
    secret: process.env.AUTH_SECRET,
});
