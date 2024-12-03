import tkinter as tk
from tkinter import filedialog, messagebox, font
from tkinter import ttk
import markdown
from tkhtmlview import HTMLLabel
from pygments import highlight
from pygments.lexers import MarkdownLexer
from pygments.formatters import HtmlFormatter
import mdformat
import yaml
import re

class MarkdownEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Markdown Editor")
        self.current_file = None
        
        # Configure window size
        self.root.geometry("1200x800")
        
        # Create main container
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(expand=True, fill='both', padx=5, pady=5)
        
        # Create left frame for editing
        self.left_frame = ttk.Frame(self.paned)
        self.paned.add(self.left_frame, weight=1)
        
        # Create toolbar
        self.create_toolbar()
        
        # Create main text area with line numbers
        self.text_frame = ttk.Frame(self.left_frame)
        self.text_frame.pack(expand=True, fill='both')
        
        self.line_numbers = tk.Text(self.text_frame, width=4, padx=3, takefocus=0, border=0,
                                  background='lightgray', state='disabled')
        self.line_numbers.pack(side=tk.LEFT, fill='y')
        
        # Create text area with syntax highlighting tags
        self.text_area = tk.Text(self.text_frame, wrap=tk.WORD, undo=True)
        self.text_area.pack(side=tk.LEFT, expand=True, fill='both')
        
        # Configure tags for syntax highlighting
        self.text_area.tag_configure("frontmatter", foreground="#6c71c4")
        self.text_area.tag_configure("error_heading", background="#FFD6D6")
        self.text_area.tag_configure("error_list", background="#FFD6D6")
        self.text_area.tag_configure("error_link", background="#FFD6D6")
        self.text_area.tag_configure("error_frontmatter", background="#FFD6D6")
        
        # Create tooltip
        self.tooltip = tk.Label(self.root, text="", background="#ffffe0", relief="solid", borderwidth=1)
        self.tooltip.pack_forget()
        
        # Create right frame for preview
        self.right_frame = ttk.Frame(self.paned)
        self.paned.add(self.right_frame, weight=1)
        
        # Create preview area
        self.preview_label = HTMLLabel(self.right_frame, html="<h1>Preview</h1>")
        self.preview_label.pack(expand=True, fill='both', padx=5, pady=5)
        
        # Create status bar with lint indicator
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.lint_indicator = ttk.Label(self.status_frame, text="✓ No Issues", foreground='green')
        self.lint_indicator.pack(side=tk.RIGHT, padx=5)
        
        self.status_bar = ttk.Label(self.status_frame, text="Line: 1, Column: 0")
        self.status_bar.pack(side=tk.LEFT, fill=tk.X)
        
        # Create menu bar
        self.create_menu()
        
        # Bind events
        self.text_area.bind('<Key>', self.on_text_change)
        self.text_area.bind('<KeyRelease>', self.on_text_change)
        self.text_area.bind('<Button-1>', self.update_status_bar)
        self.text_area.bind('<ButtonRelease-1>', self.update_status_bar)
        self.text_area.bind('<Motion>', self.show_tooltip)
        self.text_area.bind('<Leave>', lambda e: self.tooltip.pack_forget())
        
        # Initial line numbers
        self.update_line_numbers()

    def show_tooltip(self, event):
        """Show tooltip with error message when hovering over highlighted text"""
        index = self.text_area.index(f"@{event.x},{event.y}")
        tags = self.text_area.tag_names(index)
        
        error_messages = {
            "error_heading": "Missing space after heading #",
            "error_list": "Missing space after list marker",
            "error_link": "Empty link detected",
            "error_frontmatter": "Invalid YAML frontmatter"
        }
        
        for tag in tags:
            if tag in error_messages:
                # Get the bbox of the current character
                bbox = self.text_area.bbox(index)
                if bbox:
                    x, y, _, height = bbox
                    
                    # Position tooltip below the text
                    root_x = self.text_area.winfo_rootx() + x
                    root_y = self.text_area.winfo_rooty() + y + height
                    
                    self.tooltip.config(text=error_messages[tag])
                    self.tooltip.place(x=root_x, y=root_y)
                return
                
        self.tooltip.pack_forget()

    def clear_error_tags(self):
        """Clear all error highlighting tags"""
        for tag in ["error_heading", "error_list", "error_link", "error_frontmatter"]:
            self.text_area.tag_remove(tag, "1.0", tk.END)

    def lint_markdown(self):
        """Check markdown content for common issues while ignoring frontmatter"""
        content = self.text_area.get(1.0, tk.END)
        issues = []
        
        # Clear previous error highlights
        self.clear_error_tags()
        
        # Extract and validate frontmatter if present
        if self.has_frontmatter(content):
            frontmatter, is_valid = self.extract_frontmatter(content)
            if not is_valid:
                issues.append("Invalid YAML frontmatter")
                # Highlight invalid frontmatter
                pattern = r'^---\s*\n.*?\n---\s*\n'
                match = re.match(pattern, content, re.DOTALL)
                if match:
                    end_index = f"1.0+{len(match.group(0))}c"
                    self.text_area.tag_add("error_frontmatter", "1.0", end_index)
            
            # Remove frontmatter for markdown validation
            pattern = r'^---\s*\n.*?\n---\s*\n'
            content = re.sub(pattern, '', content, count=1, flags=re.DOTALL)
        
        # Check for common markdown issues
        if content.strip():
            # Check for spaces after list markers
            for match in re.finditer(r'^(\s*[-*+])([^\s])', content, re.MULTILINE):
                issues.append("Missing space after list marker")
                start = match.start(1)
                end = match.end(2)
                # Convert character position to line.char format
                content_before = content[:start]
                line = content_before.count('\n') + 1
                col = len(content_before.split('\n')[-1])
                start_index = f"{line}.{col}"
                content_before = content[:end]
                line = content_before.count('\n') + 1
                col = len(content_before.split('\n')[-1])
                end_index = f"{line}.{col}"
                self.text_area.tag_add("error_list", start_index, end_index)
            
            # Check for consistent heading style
            for match in re.finditer(r'(#[^#\s])', content):
                issues.append("Missing space after heading #")
                start = match.start(1)
                end = match.end(1)
                # Convert character position to line.char format
                content_before = content[:start]
                line = content_before.count('\n') + 1
                col = len(content_before.split('\n')[-1])
                start_index = f"{line}.{col}"
                content_before = content[:end]
                line = content_before.count('\n') + 1
                col = len(content_before.split('\n')[-1])
                end_index = f"{line}.{col}"
                self.text_area.tag_add("error_heading", start_index, end_index)
            
            # Check for empty links
            for match in re.finditer(r'(\[\]\(\))', content):
                issues.append("Empty links detected")
                start = match.start(1)
                end = match.end(1)
                # Convert character position to line.char format
                content_before = content[:start]
                line = content_before.count('\n') + 1
                col = len(content_before.split('\n')[-1])
                start_index = f"{line}.{col}"
                content_before = content[:end]
                line = content_before.count('\n') + 1
                col = len(content_before.split('\n')[-1])
                end_index = f"{line}.{col}"
                self.text_area.tag_add("error_link", start_index, end_index)
        
        # Update lint indicator
        if issues:
            self.lint_indicator.config(text=f"⚠ {len(issues)} Issues", foreground='red')
        else:
            self.lint_indicator.config(text="✓ No Issues", foreground='green')

    def has_frontmatter(self, content):
        """Check if content has YAML frontmatter"""
        pattern = r'^---\s*\n.*?\n---\s*\n'
        return bool(re.match(pattern, content, re.DOTALL))

    def extract_frontmatter(self, content):
        """Extract YAML frontmatter from content"""
        pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.match(pattern, content, re.DOTALL)
        if match:
            try:
                frontmatter = yaml.safe_load(match.group(1))
                return frontmatter, True
            except yaml.YAMLError:
                return None, False
        return None, False

    def format_markdown(self):
        """Format the current markdown content using mdformat while preserving frontmatter"""
        try:
            content = self.text_area.get(1.0, tk.END)
            has_frontmatter = self.has_frontmatter(content)
            
            if has_frontmatter:
                # Split content into frontmatter and markdown
                pattern = r'^---\s*\n.*?\n---\s*\n'
                parts = re.split(pattern, content, maxsplit=1, flags=re.DOTALL)
                if len(parts) > 1:
                    frontmatter = re.match(pattern, content, re.DOTALL).group(0)
                    markdown_content = parts[1]
                    
                    # Format only the markdown part
                    formatted_markdown = mdformat.text(markdown_content)
                    
                    # Combine frontmatter and formatted markdown
                    formatted_content = frontmatter + formatted_markdown
                else:
                    formatted_content = mdformat.text(content)
            else:
                formatted_content = mdformat.text(content)
                
            self.text_area.delete(1.0, tk.END)
            self.text_area.insert(1.0, formatted_content)
            self.highlight_frontmatter()
            self.lint_indicator.config(text="✓ Formatted", foreground='green')
        except Exception as e:
            self.lint_indicator.config(text="⚠ Format Error", foreground='red')
            messagebox.showerror("Format Error", str(e))

    def highlight_frontmatter(self):
        """Highlight YAML frontmatter"""
        content = self.text_area.get(1.0, tk.END)
        if self.has_frontmatter(content):
            pattern = r'^---\s*\n.*?\n---\s*\n'
            match = re.match(pattern, content, re.DOTALL)
            if match:
                end_index = f"1.0+{len(match.group(0))}c"
                self.text_area.tag_add("frontmatter", "1.0", end_index)

    def insert_markdown(self, mark):
        if self.text_area.tag_ranges(tk.SEL):
            start = self.text_area.index(tk.SEL_FIRST)
            end = self.text_area.index(tk.SEL_LAST)
            selected_text = self.text_area.get(start, end)
            self.text_area.delete(start, end)
            self.text_area.insert(start, f"{mark}{selected_text}{mark}")
        else:
            self.text_area.insert(tk.INSERT, mark)
            
    def insert_link(self):
        if self.text_area.tag_ranges(tk.SEL):
            start = self.text_area.index(tk.SEL_FIRST)
            end = self.text_area.index(tk.SEL_LAST)
            selected_text = self.text_area.get(start, end)
            self.text_area.delete(start, end)
            self.text_area.insert(start, f"[{selected_text}](url)")
        else:
            self.text_area.insert(tk.INSERT, "[text](url)")
            
    def update_line_numbers(self):
        lines = self.text_area.get(1.0, tk.END).count('\n')
        line_numbers_text = '\n'.join(str(i) for i in range(1, lines + 1))
        self.line_numbers.config(state='normal')
        self.line_numbers.delete(1.0, tk.END)
        self.line_numbers.insert(1.0, line_numbers_text)
        self.line_numbers.config(state='disabled')
        
    def update_status_bar(self, event=None):
        cursor_position = self.text_area.index(tk.INSERT)
        line, column = cursor_position.split('.')
        self.status_bar['text'] = f"Line: {line}, Column: {column}"
        
    def on_text_change(self, event=None):
        self.update_line_numbers()
        self.update_preview()
        self.update_status_bar()
        self.highlight_frontmatter()
        self.lint_markdown()
        
    def update_preview(self):
        content = self.text_area.get(1.0, tk.END)
        html = markdown.markdown(content, extensions=['fenced_code', 'tables'])
        self.preview_label.set_html(html)
        
    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New", command=self.new_file)
        file_menu.add_command(label="Open", command=self.open_file)
        file_menu.add_command(label="Save", command=self.save_file)
        file_menu.add_command(label="Save As", command=self.save_as_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
    def new_file(self):
        self.text_area.delete(1.0, tk.END)
        self.current_file = None
        self.root.title("Markdown Editor")
        
    def open_file(self):
        file_path = filedialog.askopenfilename(
            defaultextension=".md",
            filetypes=[("Markdown Files", "*.md"), ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    self.text_area.delete(1.0, tk.END)
                    self.text_area.insert(1.0, content)
                self.current_file = file_path
                self.root.title(f"Markdown Editor - {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file: {str(e)}")
                
    def save_file(self):
        if self.current_file:
            try:
                content = self.text_area.get(1.0, tk.END)
                with open(self.current_file, 'w', encoding='utf-8') as file:
                    file.write(content)
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file: {str(e)}")
        else:
            self.save_as_file()
            
    def save_as_file(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown Files", "*.md"), ("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if file_path:
            self.current_file = file_path
            self.save_file()
            self.root.title(f"Markdown Editor - {file_path}")

    def create_toolbar(self):
        toolbar = ttk.Frame(self.left_frame)
        toolbar.pack(fill=tk.X, padx=5, pady=2)
        
        # Create toolbar buttons
        bold_btn = ttk.Button(toolbar, text="B", width=3, command=lambda: self.insert_markdown("**"))
        bold_btn.pack(side=tk.LEFT, padx=2)
        
        italic_btn = ttk.Button(toolbar, text="I", width=3, command=lambda: self.insert_markdown("*"))
        italic_btn.pack(side=tk.LEFT, padx=2)
        
        heading_btn = ttk.Button(toolbar, text="H", width=3, command=lambda: self.insert_markdown("#"))
        heading_btn.pack(side=tk.LEFT, padx=2)
        
        link_btn = ttk.Button(toolbar, text="Link", width=5, command=self.insert_link)
        link_btn.pack(side=tk.LEFT, padx=2)
        
        list_btn = ttk.Button(toolbar, text="List", width=5, command=lambda: self.insert_markdown("- "))
        list_btn.pack(side=tk.LEFT, padx=2)
        
        code_btn = ttk.Button(toolbar, text="Code", width=5, command=lambda: self.insert_markdown("`"))
        code_btn.pack(side=tk.LEFT, padx=2)
        
        # Add Format button
        format_btn = ttk.Button(toolbar, text="Format", width=6, command=self.format_markdown)
        format_btn.pack(side=tk.LEFT, padx=2)

if __name__ == "__main__":
    root = tk.Tk()
    app = MarkdownEditor(root)
    root.mainloop()
