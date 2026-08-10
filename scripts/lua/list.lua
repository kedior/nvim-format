local ok, err = pcall(function()
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
	io.stdout:write("FTS:" .. vim.json.encode(conform.formatters_by_ft) .. "\n")
end)
if not ok then
	io.stdout:write("ERR:" .. tostring(err) .. "\n")
end
