FROM node:18
WORKDIR /app
COPY . .
RUN npm config set registry https://registry.npmmirror.com
RUN npm install --verbose
RUN npm install -g serve
RUN npm run build
CMD ["serve", "-s", "build", "-l", "3000"]
