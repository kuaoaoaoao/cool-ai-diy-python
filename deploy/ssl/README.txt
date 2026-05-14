# SSL证书配置说明

## 1. 使用Let's Encrypt免费证书（推荐）

### 安装certbot
```bash
# Ubuntu/Debian
apt-get install certbot

# CentOS/RHEL
yum install certbot
```

### 获取证书
```bash
# 替换 your-domain.com 为你的实际域名
certbot certonly --standalone -d api.coolai.com -d www.coolai.com -d coolai.com
```

### 复制证书到本目录
```bash
cp /etc/letsencrypt/live/coolai.com/fullchain.pem ./fullchain.pem
cp /etc/letsencrypt/live/coolai.com/privkey.pem ./privkey.pem
```

### 自动续期（cron）
```bash
# 添加crontab任务，每天检查续期
0 0 * * * certbot renew --quiet && cp /etc/letsencrypt/live/coolai.com/*.pem /path/to/deploy/ssl/ && docker-compose restart nginx
```

## 2. 使用自签名证书（开发环境）

```bash
# 生成自签名证书
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout privkey.pem \
  -out fullchain.pem \
  -subj "/CN=localhost"
```

## 3. docker-compose挂载

确保 docker-compose.yml 中 nginx 服务的 volumes 包含：
```yaml
volumes:
  - ./deploy/ssl:/etc/nginx/ssl:ro
```

## 注意事项
- 证书文件不要提交到Git
- 生产环境必须使用正规CA签发的证书
- HTTP到HTTPS重定向在nginx.conf中默认注释，部署后取消注释
