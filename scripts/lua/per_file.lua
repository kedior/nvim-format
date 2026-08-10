-- 占位符(__XXX__)由 Python 在运行时替换为真实值,此处仅为消除 LSP 的 undefined-global 提示
---@diagnostic disable: undefined-global
local ok, err = pcall(function()
	-- 防止 LazyVim 默认的 autowrite 在切换 buffer 时把格式化结果意外写回原文件
	vim.opt.autowrite = false
	vim.opt.autowriteall = false
	local p = vim.fn.readfile("__PATH_FILE__")[1]
	vim.cmd("edit " .. vim.fn.fnameescape(p))
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
		error("无法加载 conform.nvim(本工具以 conform.nvim 为格式化依据): " .. tostring(conform))
	end
	local names = conform.list_formatters_for_buffer(0)
	io.stdout:write("NAMES:" .. vim.json.encode(names) .. "\n")
	local infos = {}
	for _, n in ipairs(names) do
		local i = conform.get_formatter_info(n, 0)
		infos[#infos + 1] = { name = n, available = i and i.available, msg = i and i.available_msg }
	end
	io.stdout:write("INFO:" .. vim.json.encode(infos) .. "\n")
	local lsp_mode = conform.default_format_opts.lsp_format or "never"
	io.stdout:write("LSP_MODE:" .. tostring(lsp_mode) .. "\n")
	local lsp_attached = false
	if #names == 0 and lsp_mode ~= "never" and __ALLOW_LSP__ then
		lsp_attached = vim.wait(__WAIT_MS__, function()
			for _, c in ipairs(vim.lsp.get_clients({ bufnr = 0 })) do
				local cap = c.server_capabilities
				if cap and (cap.documentFormattingProvider or cap.documentRangeFormattingProvider) then
					return true
				end
			end
			return false
		end)
		local cl = {}
		for _, c in ipairs(vim.lsp.get_clients({ bufnr = 0 })) do
			cl[#cl + 1] = c.name
		end
		io.stdout:write("CLIENTS:" .. vim.json.encode(cl) .. "\n")
		io.stdout:write("LSP_ATTACHED:" .. tostring(lsp_attached) .. "\n")
	end
	local r = conform.format({ bufnr = 0, timeout_ms = __FMT_TIMEOUT_MS__ })
	-- conform.format 在 async=false 下是同步的,返回时 buffer 已是最新
	local modified = vim.bo.modified
	io.stdout:write("FMT:" .. vim.json.encode({ ok = true, did_edit = r == true, modified = modified }) .. "\n")
	if modified then
		local wcmd = "write!"
		if __OUT_FILE__ then
			wcmd = "write! " .. vim.fn.fnameescape(__OUT_FILE__)
		end
		local wok, werr = pcall(function()
			vim.cmd(wcmd)
		end)
		io.stdout:write("WROTE:" .. vim.json.encode({ ok = wok, err = tostring(werr) }) .. "\n")
	end
end)
if not ok then
	io.stdout:write("FMT:" .. vim.json.encode({ ok = false, err = tostring(err) }) .. "\n")
end
