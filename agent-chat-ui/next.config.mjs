/** @type {import('next').NextConfig} */
const nextConfig = {
  // Daytona SDK / ws 在服务端 route 里走原生绑定；webpack 打包会踩坑，
  // 保持 external 让 Node 自己 require。
  serverExternalPackages: ["ws", "@daytona/sdk"],
  experimental: {
    serverActions: {
      bodySizeLimit: "10mb",
    },
  },
};

export default nextConfig;
