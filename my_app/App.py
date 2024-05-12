import tkinter as tk
from tkinter import ttk
import requests
from threading import Thread
import textwrap
import base64
from io import BytesIO
import os
from pathlib import Path
import google.generativeai as genai
from PyPDF2 import PdfReader

api_key = "SUA KEY AQUI"

class AutoCompleteEntry(ttk.Entry):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.var = tk.StringVar()
        self.config(textvariable=self.var)

        self.listbox_up = False
        self.current = 0

class Application(ttk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.create_widgets()

    def create_widgets(self):
        print("Diretório de Trabalho Atual:", )
        with open("my_app//logo.b64", "rb") as file:
            base64_image = file.read()
        image_data = base64.b64decode(base64_image)
        image = tk.PhotoImage(data=image_data)
        
        # Widget para exibir a imagem
        image_label = tk.Label(self, image=image)
        image_label.image = image  # Mantém uma referência!
        image_label.grid(row=0, column=0, columnspan=2, pady=10, padx=10, sticky="ew")

        ttk.Label(self, text="Nome do Medicamento:").grid(row=1, column=0, padx=10, pady=0, sticky=tk.W)
        self.medicine_entry = AutoCompleteEntry(self, width=66)
        self.medicine_entry.grid(row=1, column=1, padx=10, pady=0, sticky=tk.W)

        ttk.Label(self, text="Pergunta:").grid(row=2, column=0, padx=10, pady=0, sticky=tk.W)
        self.question_entry = ttk.Entry(self, width=66)
        self.question_entry.grid(row=2, column=1, padx=10, pady=10, sticky=tk.W)

        ttk.Label(self, text="Resposta:").grid(row=3, column=0, padx=10, pady=10, sticky=tk.NW)
        self.answer_text = tk.Text(self, height=20, width=50)  # Doubled the height
        self.answer_text.grid(row=3, column=1, padx=10, pady=10, sticky=tk.W)

        self.ask_button = ttk.Button(self, text="Perguntar", command=self.ask_question)
        self.ask_button.grid(row=4, column=1, padx=10, pady=10, sticky=tk.E)

        self.grid(padx=10, pady=10)
   
    def ask_question(self):
        self.answer_text.delete('1.0', tk.END)
        medicine_name = self.medicine_entry.get().strip()  # Remove espaços em branco dos lados
        if not medicine_name:  # Verifica se a string é vazia
            self.answer_text.insert(tk.END,  "Atenção Por favor, digite o nome do medicamento.")
            return
        question = self.question_entry.get().strip() 
        if not question:  # Verifica se a string é vazia
            self.answer_text.insert(tk.END,  "Atenção Por favor, digite a pergunta.")
            return
        self.answer_text.insert(tk.END,  "Aguarde....")
        codigo = self.bulario(self.medicine_entry.get())
        self.answer_text.delete('1.0', tk.END)
        if "medicamento não encontrado." in codigo:
            self.answer_text.insert(tk.END,  "medicamento não encontrado.")
            return
        
        if self.download_pdf(codigo):
            response = self.gemini(self.question_entry.get(), "bula.pdf")
        else:
            self.answer_text.insert(tk.END,  "medicamento não encontrado.")
            return
                                    
        formatted_response = textwrap.fill(response, width=80, subsequent_indent='    ')
        self.answer_text.insert(tk.END, formatted_response + "\n")
        
    def bulario(self, remedio):
        while True:
                try:
                    base_url = 'https://consultas.anvisa.gov.br/api/consulta/bulario'
                    headers = {
                        'Authorization': 'Guest',
                        'Cookie': 'FGTServer=77E1DC77AE2F953D7ED796A08A630A01A53CF6FE5FD0E106412591871F9A9BBCFBDEA0AD564FD89D3BDE8278200B; _cfuvid=rGNLFpfJ9I5L5_5GVmsh_NWPDHP6ohltdNn_bkbiCcU-1715440297140-0.0.1.1-604800000'
                    }

                    # Primeira requisição para obter o número total de páginas
                    response = requests.get(f'{base_url}?count=1&filter%5BnomeProduto%5D={remedio}', headers=headers)
                    data = response.json()        
                    if data['numberOfElements'] > 0 :
                        return data['content'][0]['idBulaProfissionalProtegido']
                    else:
                        return "medicamento não encontrado."
                except Exception as e:
                    print(f"An error occurred while fetching page : {e}")

    def extract_pdf_pages(self, pathname: str) -> list[str]:
        parts = [f"--- START OF PDF ${pathname} ---"]
        reader = PdfReader(pathname)
        pages = []
        for index, page in enumerate(reader.pages):
            text = page.extract_text()
            parts.append(f"--- PAGE {index} ---")
            parts.append(text)
        return parts
    
    def gemini(self, question, path_pdf):
        genai.configure(api_key=api_key)

        generation_config = {
        "temperature": 0,
        "top_p": 0,
        "top_k": 0,
        "max_output_tokens": 8192,
        }
        safety_settings = [ 
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        ]
        model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest",
                                generation_config=generation_config,
                                safety_settings=safety_settings)

        prompt_parts = [
            *self.extract_pdf_pages(path_pdf), # Substitua pelo caminho real do seu PDF
            "\n sou médico e quero saber:"+ question +"  você deve responder apenas sobre o que eu perguntei e com dados que eu passei da bula.\n\n",
        ]

        response = model.generate_content(prompt_parts)
        return response.text
    
    def download_pdf(self, codigo):
        url = "https://consultas.anvisa.gov.br/api/consulta/medicamentos/arquivo/bula/parecer/"+codigo+"/?Authorization="
        print(url)
        filename = "bula.pdf"  # Nome do arquivo onde o PDF será salvo
        # Faz o request para obter o conteúdo do PDF
        response = requests.get(url)
        # Verifica se o request foi bem-sucedido (código de status 200)
        if response.status_code == 200:
            # Abre o arquivo no modo de escrita binária
            with open(filename, 'wb') as f:
                # Escreve o conteúdo do PDF no arquivo
                f.write(response.content)
            print(f"Download do PDF concluído: {filename}")
            return True
        else:
            print(f"Erro ao fazer o download do PDF: Status Code {response.status_code}")
            return False
root = tk.Tk()
root.title("AURAMED IA")
root.geometry("600x700")
root.resizable()
app = Application(master=root)
app.mainloop()
