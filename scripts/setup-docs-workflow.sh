#!/bin/bash
# 设置文档管理工作流

echo "🚀 设置项目文档管理工作流..."

# 1. 创建scripts目录
mkdir -p scripts

# 2. 设置Git commit模板
git config --global commit.template .gitmessage

# 3. 创建post-commit hook
cat > .git/hooks/post-commit << 'EOF'
#!/bin/bash
echo ""
echo "✅ 提交成功！"
echo "📝 如果是新功能或重要修改，请记得更新 PROGRESS.md"
echo ""
EOF
chmod +x .git/hooks/post-commit

# 4. 设置自动fetch
git config --global fetch.prune true
git config --global pull.rebase false

echo "✅ 设置完成！"
echo ""
echo "📋 使用说明:"
echo "  1. 提交代码时会自动打开commit模板"
echo "  2. 提交后会提醒更新PROGRESS.md"
echo "  3. 使用 scripts/update-progress.sh 快速更新进度"
