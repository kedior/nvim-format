-- 占位符(__XXX__)由 Python 在运行时替换为真实值,此处仅为消除 LSP 的 undefined-global 提示
---@diagnostic disable: undefined-global
local list_file = "__LIST_FILE__"
local out_file = "__OUT_FILE__"
local ok, err = pcall(function()
	-- 关键:关闭 autowrite(否则 :edit 切换 buffer 时会把 LSP 异步修改的 buffer 写回原文件),
	-- 保持 hidden(允许带修改的 buffer 被切换)
	vim.opt.autowrite = false
	vim.opt.autowriteall = false
	vim.opt.hidden = true
	local lazy_ok, lazy = pcall(require, "lazy")
	if lazy_ok then
		lazy.load({ plugins = { "conform.nvim" } })
	end
	local cok, conform = pcall(require, "conform")
	if not cok then
		vim.cmd("packloadall")
		cok, conform = pcall(require, "conform")
	end
	if not cok then
		error("无法加载 conform.nvim: " .. tostring(conform))
	end
	local lsp_mode = conform.default_format_opts.lsp_format or "never"
	local files = vim.fn.readfile(list_file)
	local results = {}
	for i, path in ipairs(files) do
		local r = { path = path }
		local eok, eerr = pcall(function()
			vim.cmd("edit " .. vim.fn.fnameescape(path))
		end)
		if not eok then
			r.status, r.msg = "error", "打开文件失败: " .. tostring(eerr)
		else
			local names = conform.list_formatters_for_buffer(0)
			local needs_lsp = #names == 0 and lsp_mode ~= "never" and __ALLOW_LSP__
			local attached = false
			if needs_lsp then
				attached = vim.wait(__WAIT_MS__, function()
					for _, cl in ipairs(vim.lsp.get_clients({ bufnr = 0 })) do
						local cap = cl.server_capabilities
						if cap and (cap.documentFormattingProvider or cap.documentRangeFormattingProvider) then
							return true
						end
					end
					return false
				end)
			end
			if #names == 0 and not attached then
				r.status = "skipped"
			else
				local fok, fr = pcall(function()
					return conform.format({ bufnr = 0, timeout_ms = __FMT_TIMEOUT_MS__ })
				end)
				if not fok then
					r.status, r.msg = "error", "格式化失败: " .. tostring(fr)
				else
					-- conform.format 在 async=false 下是同步的,返回时 buffer 已是最新
					-- (有变化的文件已是格式化结果,无变化的文件内容不变,无需任何等待)
					local tmp = vim.fn.fnamemodify(path, ":p:h") .. "/.nvfmt-tmp-" .. vim.fn.fnamemodify(path, ":t")
					r.status, r.tmp = "done", tmp
					r.wrote = pcall(function()
						vim.cmd("silent! write! " .. vim.fn.fnameescape(tmp))
					end)
				end
			end
		end
		results[i] = r
	end
	vim.fn.writefile({ vim.json.encode(results) }, out_file)
end)
if not ok then
	vim.fn.writefile({ vim.json.encode({ fatal = tostring(err) }) }, "__OUT_FILE__")
end
