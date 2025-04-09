from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import os

# Configura o Chrome sem precisar baixar driver manualmente
options = Options()
options.add_argument('--headless')
options.add_argument('--disable-gpu')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

base_url = 'https://ai.google.dev'

# Acessa a página principal
driver.get(f'{base_url}/gemini-api/docs?hl=pt-br')
time.sleep(5)

# Cria a pasta para salvar os arquivos
os.makedirs('gemini_docs', exist_ok=True)

# Coleta os links do menu lateral
menu_links = driver.find_elements(By.CSS_SELECTOR, 'nav a')
links = []
for link in menu_links:
    href = link.get_attribute('href')
    if href and href.startswith(base_url) and href not in links:
        links.append(href)

# Visita cada link e salva o conteúdo como .txt
for i, link in enumerate(links):
    driver.get(link)
    time.sleep(3)
    body = driver.find_element(By.TAG_NAME, 'body').text
    with open(f'gemini_docs/page_{i+1}.txt', 'w', encoding='utf-8') as f:
        f.write(f'URL: {link}\n\n{body}')
    print(f'Salvo: page_{i+1}.txt')

driver.quit()
