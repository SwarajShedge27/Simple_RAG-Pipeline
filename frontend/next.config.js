/** @type {import('next').NextConfig} */
const { TracewayDebugIdsWebpackPlugin } = require("@tracewayapp/bundler-plugin/webpack");

const nextConfig = {
    eslint: {
        ignoreDuringBuilds: true,
    },
    productionBrowserSourceMaps: true,
    webpack: (config, { dev, isServer }) => {
        if (!dev && !isServer) {
            config.plugins.push(new TracewayDebugIdsWebpackPlugin());
        }

        return config;
    },
};

module.exports = nextConfig;
