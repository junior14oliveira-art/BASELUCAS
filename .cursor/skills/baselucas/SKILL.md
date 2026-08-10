---
name: baselucas
description: Regras obrigatórias de segurança e versionamento para o projeto. Exige que o agente leia a documentação antes de codificar, crie um commit de backup (ponto de restauração) antes de alterações e faça um git push automático após finalizar.
allowed-tools:
  - "Read"
  - "Write"
  - "Bash"
---

# Skill: Fluxo de Trabalho Seguro (Git e Leitura)

> [!CAUTION]
> **REGRA OBRIGATÓRIA DA EQUIPE:** O mantenedor do projeto exigiu que todos os agentes de IA obedeçam a este fluxo de trabalho sem exceções para evitar perda de dados e regressões.

Sempre que você, agente, for instruído a realizar uma alteração no código deste repositório, você **deve** seguir rigorosamente o seguinte pipeline:

## Passo 1: Leitura Obrigatória de Contexto
- Antes de fazer qualquer alteração no código-fonte, você deve ler a documentação do projeto que for relevante à sua tarefa. 
- Ferramentas: Use `view_file` e `list_dir` na pasta `docs/` e na pasta `.agents/skills/`.
- Nunca assuma arquiteturas. Confirme com a documentação atual do projeto (ex: `omnichannel-hub`).

## Passo 2: Ponto de Restauração (Backup Local)
- Antes de aplicar um plano de implementação (edição pesada), você deve garantir que o trabalho atual está a salvo.
- Execute o comando no terminal (powershell):
  ```bash
  git add .
  git commit -m "chore: ponto de restauracao antes de alteracao pelo agente"
  ```
- Isso garante que se o código que você escrever quebrar tudo, o usuário pode voltar atrás facilmente.

## Passo 3: Execução (Mão no Código)
- Edite os arquivos livremente cumprindo as instruções do usuário e garantindo que o código não está quebrando a lógica estabelecida no Passo 1.

## Passo 4: Push Automático para o GitHub
- Assim que o recurso estiver pronto, testado e validado pelo usuário, você deve subir o código.
- Execute os seguintes comandos no terminal do repositório:
  ```bash
  git add .
  git commit -m "feat: [Descreva exatamente qual funcionalidade voce acabou de concluir]"
  git push
  ```
- Avise o usuário explicitamente de que a alteração foi concluída e salva no GitHub.
