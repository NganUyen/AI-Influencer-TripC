FROM ghcr.io/growchief/growchief:latest

WORKDIR /usr/src/app

# GrowChief currently invokes an unpinned `pnpm dlx prisma`, which now resolves
# Prisma 7 and breaks its Prisma 6-era schema on startup. Keep the public image,
# but pin the runtime CLI to the app's matching Prisma 6 line.
RUN node -e "const fs=require('fs'); const path='package.json'; const pkg=JSON.parse(fs.readFileSync(path,'utf8')); pkg.scripts['prisma-generate']='pnpm dlx prisma@6.13.0 generate --schema ./schema.prisma'; pkg.scripts['prisma-db-push']='pnpm dlx prisma@6.13.0 db push --schema ./schema.prisma'; fs.writeFileSync(path, JSON.stringify(pkg, null, 2)+'\n')"
RUN pnpm dlx prisma@6.13.0 --version
