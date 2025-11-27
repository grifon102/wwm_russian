import csv
import sys
import os
from collections import defaultdict
import tkinter as tk
from tkinter import filedialog, messagebox

def load_dictionary(filepath, delimiter='\t'):
    # List of (term, translation) tuples to preserve duplicates if they exist with diff translations
    dictionary = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=delimiter)
            header = next(reader, None) # Skip header
            for row in reader:
                if len(row) >= 2:
                    term = row[0].strip()
                    translation = row[1].strip()
                    if term: # Only add non-empty terms
                        dictionary.append((term, translation))
    except Exception as e:
        print(f"Error reading dictionary: {e}")
        sys.exit(1)
    return dictionary

def load_translations(filepath):
    text_to_ids = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            header = next(reader, None) # Skip header
            for row in reader:
                if len(row) >= 2:
                    id_val = row[0].strip()
                    text = row[1].strip()
                    if text:
                        if text not in text_to_ids:
                            text_to_ids[text] = []
                        text_to_ids[text].append(id_val)
    except Exception as e:
        print(f"Error reading translations: {e}")
        sys.exit(1)
    return text_to_ids

def find_matches(dictionary, text_to_ids, output_file, headers=['EN', 'RUS', 'ID']):
    print(f"Processing {len(text_to_ids)} unique texts against {len(dictionary)} dictionary terms...")
    
    # Map (term, translation) -> set of IDs
    # We group by both to handle cases where the same term might have multiple entries/translations
    match_map = defaultdict(set)
    
    match_count = 0
    
    # Optimization: Convert dictionary to a list for faster iteration if needed, 
    # but here we iterate it for every text.
    
    for text, ids in text_to_ids.items():
        # Check each dictionary term against the text
        for term, translation in dictionary:
            if term in text:
                match_map[(term, translation)].update(ids)
                match_count += 1
                    
    print(f"Done processing. Found matches for {len(match_map)} dictionary entries.")
    
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        # Header
        writer.writerow(headers)
        
        # Sort by term for consistent output
        sorted_keys = sorted(match_map.keys(), key=lambda x: x[0])
        
        for term, translation in sorted_keys:
            # Sort IDs for consistent output
            ids_list = sorted(list(match_map[(term, translation)]))
            ids_str = ';'.join(ids_list)
            
            writer.writerow([term, translation, ids_str])

    print(f"Saved to {output_file}")

def extract_unique_strings(matches_file, source_file, output_file):
    target_ids = set()
    try:
        with open(matches_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            next(reader, None) # Skip header
            for row in reader:
                if len(row) >= 3:
                    ids = row[2].split(';')
                    for i in ids:
                        if i.strip():
                            target_ids.add(i.strip())
    except Exception as e:
        raise Exception(f"Error reading matches file: {e}")

    count = 0
    try:
        with open(output_file, 'w', encoding='utf-8', newline='') as f_out:
            writer = csv.writer(f_out, delimiter='\t')
            writer.writerow(['ID', 'OriginalText'])
            
            with open(source_file, 'r', encoding='utf-8') as f_in:
                reader = csv.reader(f_in, delimiter='\t')
                next(reader, None) # Skip header
                for row in reader:
                    if len(row) >= 2:
                        id_val = row[0].strip()
                        if id_val in target_ids:
                            writer.writerow(row[:2])
                            count += 1
    except Exception as e:
        raise Exception(f"Error processing files: {e}")
        
    return count

class MatcherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dictionary Matcher")
        self.root.geometry("800x350")

        self.base_dir = os.getcwd()
        
        # Default paths
        default_dict = os.path.join(self.base_dir, 'docs', 'dictionary.tsv')
        default_trans = os.path.join(self.base_dir, 'translation_en.tsv')
        default_output = os.path.join(self.base_dir, 'dictionary_matches.tsv')

        # Variables
        self.dict_path = tk.StringVar(value=default_dict)
        self.trans_path = tk.StringVar(value=default_trans)
        self.output_path = tk.StringVar(value=default_output)

        # UI Layout
        self.create_row("Dictionary Path:", self.dict_path, self.browse_dict, 0)
        self.create_row("Translation Path:", self.trans_path, self.browse_trans, 1)
        self.create_row("Output Path:", self.output_path, self.browse_output, 2)

        # Process Button
        btn_frame = tk.Frame(root)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=20)
        
        self.process_btn = tk.Button(btn_frame, text="Start Processing", command=self.run_processing, 
                 font=("Arial", 10, "bold"), bg="#e1e1e1", padx=20, pady=5)
        self.process_btn.pack(side=tk.LEFT, padx=10)

        self.extract_btn = tk.Button(btn_frame, text="Extract Unique Strings", command=self.run_extraction,
                 font=("Arial", 10), bg="#e1e1e1", padx=20, pady=5, state=tk.DISABLED)
        self.extract_btn.pack(side=tk.LEFT, padx=10)

        # Status
        self.status_label = tk.Label(root, text="Ready", fg="gray")
        self.status_label.grid(row=4, column=0, columnspan=3)

    def create_row(self, label, var, cmd, row_idx):
        tk.Label(self.root, text=label).grid(row=row_idx, column=0, sticky="e", padx=10, pady=10)
        tk.Entry(self.root, textvariable=var, width=60).grid(row=row_idx, column=1, padx=5, pady=10)
        tk.Button(self.root, text="Browse...", command=cmd).grid(row=row_idx, column=2, padx=10, pady=10)

    def browse_dict(self):
        path = filedialog.askopenfilename(initialdir=self.base_dir, title="Select Dictionary File", filetypes=[("TSV Files", "*.tsv"), ("All Files", "*.*")])
        if path: 
            self.dict_path.set(path)
            # Auto-switch for glossary
            if "glossary" in os.path.basename(path).lower():
                cn_path = os.path.join(self.base_dir, 'translation_cn.tsv')
                out_path = os.path.join(self.base_dir, 'matches.china.tsv')
                if os.path.exists(cn_path):
                    self.trans_path.set(cn_path)
                self.output_path.set(out_path)
            else:
                # Revert to defaults if switching back? Or just leave as is.
                # Let's leave as is to not annoy user, or maybe switch back to en if it was cn?
                # For now, just handle the glossary case explicitly.
                pass

    def browse_trans(self):
        path = filedialog.askopenfilename(initialdir=self.base_dir, title="Select Translation File", filetypes=[("TSV Files", "*.tsv"), ("All Files", "*.*")])
        if path: self.trans_path.set(path)

    def browse_output(self):
        path = filedialog.asksaveasfilename(initialdir=self.base_dir, title="Save Output As", defaultextension=".tsv", filetypes=[("TSV Files", "*.tsv"), ("All Files", "*.*")])
        if path: self.output_path.set(path)

    def run_processing(self):
        d_path = self.dict_path.get()
        t_path = self.trans_path.get()
        o_path = self.output_path.get()

        if not os.path.exists(d_path):
            messagebox.showerror("Error", f"Dictionary file not found:\n{d_path}")
            return
        if not os.path.exists(t_path):
            messagebox.showerror("Error", f"Translation file not found:\n{t_path}")
            return

        self.status_label.config(text="Processing...", fg="blue")
        self.root.update()

        try:
            # Determine mode based on filename
            is_glossary = "glossary" in os.path.basename(d_path).lower()
            
            delimiter = ',' if is_glossary else '\t'
            headers = ['zh', 'Rus', 'ID'] if is_glossary else ['EN', 'RUS', 'ID']
            
            dictionary = load_dictionary(d_path, delimiter=delimiter)
            text_to_ids = load_translations(t_path)
            find_matches(dictionary, text_to_ids, o_path, headers=headers)
            
            self.status_label.config(text="Done!", fg="green")
            self.extract_btn.config(state=tk.NORMAL)
            messagebox.showinfo("Success", f"Matches saved to:\n{o_path}")
        except Exception as e:
            self.status_label.config(text="Error", fg="red")
            messagebox.showerror("Error", f"An error occurred:\n{e}")

    def run_extraction(self):
        m_path = self.output_path.get()
        t_path = self.trans_path.get()
        d_path = os.path.join(os.path.dirname(m_path), 'differing_strings.tsv')

        if not os.path.exists(m_path):
            messagebox.showerror("Error", f"Matches file not found:\n{m_path}")
            return
        if not os.path.exists(t_path):
            messagebox.showerror("Error", f"Translation file not found:\n{t_path}")
            return

        try:
            count = extract_unique_strings(m_path, t_path, d_path)
            messagebox.showinfo("Success", f"Extracted {count} unique strings to:\n{d_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Extraction failed:\n{e}")

def main():
    root = tk.Tk()
    app = MatcherApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
