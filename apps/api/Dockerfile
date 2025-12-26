FROM node:20-alpine

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml tsconfig.base.json tsconfig.json ./
COPY packages/shared ./packages/shared
COPY apps/api ./apps/api

RUN pnpm install --no-frozen-lockfile
RUN pnpm --filter @tryfitted/shared build
RUN pnpm --filter @tryfitted/api build

EXPOSE 3001
CMD ["pnpm", "--filter", "@tryfitted/api", "start"]
