local list_file = "__LIST_FILE__"
local out_file = "__OUT_FILE__"
local ok, err = pcall(function()
	local files = vim.fn.readfile(list_file)
	local out = {}
	for i, f in ipairs(files) do
		local ft = vim.filetype.match({ filename = f }) or ""
		out[i] = { f = f, ft = ft }
	end
	vim.fn.writefile({ vim.json.encode(out) }, out_file)
end)
if not ok then
	vim.fn.writefile({ vim.json.encode({ fatal = tostring(err) }) }, out_file)
end
