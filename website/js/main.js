// Configuração de segurança
'use strict';

// Detecta protocolo e mostra aviso se não for HTTPS
if (location.protocol !== 'https:' && location.hostname !== 'localhost') {
    console.warn('Conexão não segura detectada. Recomendamos usar HTTPS.');
}

// Detecta acesso por IP direto
if (location.hostname.match(/^\d+\.\d+\.\d+\.\d+$/)) {
    document.body.innerHTML = '<div class="security-warning">Acesso direto por IP detectado. Por favor, use o domínio seguro.</div>';
}

// Scroll suave para links internos
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Animações na timeline
const observerOptions = {
    root: null,
    rootMargin: '0px',
    threshold: 0.1
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

document.querySelectorAll('.timeline-entry').forEach(entry => {
    observer.observe(entry);
});

// Carregamento de conteúdo dinâmico
class ContentLoader {
    static async loadWhitepaper() {
        try {
            const response = await fetch('/docs/whitepaper.md');
            const text = await response.text();
            document.getElementById('whitepaper-content').innerHTML = this.markdownToHtml(text);
        } catch (error) {
            console.error('Erro ao carregar whitepaper:', error);
            document.getElementById('whitepaper-content').innerHTML = '<p class="error">Erro ao carregar o whitepaper. Por favor, tente novamente mais tarde.</p>';
        }
    }

    static async loadRoadmap() {
        try {
            const [roadmapResponse, statsResponse] = await Promise.all([
                fetch('/roadmap.json'),
                fetch('/api/statistics')
            ]);
            
            const roadmap = await roadmapResponse.json();
            const stats = await statsResponse.json();
            
            this.renderRoadmap(roadmap);
            this.renderStats(stats);
        } catch (error) {
            console.error('Erro ao carregar roadmap:', error);
        }
    }

    static async loadDocumentation() {
        try {
            const docs = {
                'API': '/docs/API.md',
                'Arquitetura': '/docs/ARCHITECTURE.md',
                'Whitepaper': '/docs/whitepaper.md'
            };

            const menu = document.getElementById('docs-menu');
            const content = document.getElementById('docs-content');

            // Gera menu
            menu.innerHTML = Object.keys(docs).map((title, i) => `
                <a href="#doc-${i}" class="doc-link" data-doc="${title}">
                    ${title}
                    <span class="doc-indicator"></span>
                </a>
            `).join('');

            // Carrega documentos
            const responses = await Promise.all(
                Object.values(docs).map(path => fetch(path))
            );
            
            const contents = await Promise.all(
                responses.map(res => res.text())
            );

            // Renderiza conteúdo
            content.innerHTML = contents.map((doc, i) => `
                <div id="doc-${i}" class="doc-section">
                    ${this.markdownToHtml(doc)}
                </div>
            `).join('');

            // Adiciona eventos de clique
            menu.querySelectorAll('.doc-link').forEach((link, index) => {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    // Esconde todas as seções
                    document.querySelectorAll('.doc-section').forEach(section => {
                        section.style.display = 'none';
                    });
                    // Mostra a seção selecionada
                    document.getElementById(`doc-${index}`).style.display = 'block';
                    // Atualiza indicador ativo
                    menu.querySelectorAll('.doc-link').forEach(l => l.classList.remove('active'));
                    link.classList.add('active');
                });
            });

            // Ativa primeiro item por padrão
            menu.querySelector('.doc-link').click();

        } catch (error) {
            console.error('Erro ao carregar documentação:', error);
            document.getElementById('docs-content').innerHTML = '<p class="error">Erro ao carregar a documentação. Por favor, tente novamente mais tarde.</p>';
        }
    }

    static async loadNodeStatus() {
        try {
            const response = await fetch('/api/coordinates');
            const nodes = await response.json();
            this.renderNodeStatus(nodes);
        } catch (error) {
            console.error('Erro ao carregar status dos nós:', error);
        }
    }

    static markdownToHtml(markdown) {
        // Implementação simples de conversão MD para HTML
        return markdown
            .replace(/^# (.*$)/gm, '<h1>$1</h1>')
            .replace(/^## (.*$)/gm, '<h2>$1</h2>')
            .replace(/^### (.*$)/gm, '<h3>$1</h3>')
            .replace(/\*\*(.*)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*)\*/g, '<em>$1</em>')
            .replace(/\[([^\]]*)\]\(([^\)]*)\)/g, '<a href="$2">$1</a>')
            .replace(/`([^`]*)`/g, '<code>$1</code>')
            .replace(/```([^```]*)```/g, '<pre><code>$1</code></pre>')
            .replace(/^\s*[-*+]\s+(.*)$/gm, '<li>$1</li>')
            .split('\n\n').map(p => `<p>${p}</p>`).join('');
    }

    static renderRoadmap(roadmap) {
        const timeline = document.getElementById('roadmap-timeline');
        timeline.innerHTML = roadmap.milestones.map(milestone => `
            <article class="roadmap-entry">
                <h3>${milestone.date}</h3>
                <ul>
                    ${milestone.items.map(item => `<li>${item}</li>`).join('')}
                </ul>
            </article>
        `).join('');
    }

    static renderStats(stats) {
        const statsDiv = document.getElementById('development-stats');
        statsDiv.innerHTML = `
            <div class="stats-grid">
                <div class="stat-item">
                    <h4>Nós Ativos</h4>
                    <span>${stats.active_nodes}</span>
                </div>
                <div class="stat-item">
                    <h4>Transações/s</h4>
                    <span>${stats.tps}</span>
                </div>
                <div class="stat-item">
                    <h4>Contratos Ativos</h4>
                    <span>${stats.active_contracts}</span>
                </div>
            </div>
        `;
    }

    static renderNodeStatus(nodes) {
        const status = document.getElementById('node-status');
        status.innerHTML = `
            <div class="node-grid">
                ${nodes.map(node => `
                    <div class="node-item ${node.status}">
                        <span class="node-type">${node.type}</span>
                        <span class="node-id">${node.id}</span>
                        <span class="node-uptime">${node.uptime}s</span>
                    </div>
                `).join('')}
            </div>
        `;
    }
}

// API Explorer
class APIExplorer {
    static async init() {
        const endpoints = [
            { path: '/contracts', method: 'GET', description: 'Lista contratos' },
            { path: '/checkpoint', method: 'POST', description: 'Adiciona checkpoint' },
            { path: '/statistics', method: 'GET', description: 'Estatísticas globais' }
        ];

        const list = document.querySelector('.endpoint-list');
        const tester = document.querySelector('.endpoint-tester');

        list.innerHTML = endpoints.map(endpoint => `
            <div class="endpoint" data-path="${endpoint.path}" data-method="${endpoint.method}">
                <span class="method ${endpoint.method.toLowerCase()}">${endpoint.method}</span>
                <span class="path">${endpoint.path}</span>
                <p class="description">${endpoint.description}</p>
            </div>
        `).join('');

        list.addEventListener('click', e => {
            const endpoint = e.target.closest('.endpoint');
            if (endpoint) {
                this.showEndpointTester(endpoint.dataset.path, endpoint.dataset.method);
            }
        });
    }

    static showEndpointTester(path, method) {
        const tester = document.querySelector('.endpoint-tester');
        tester.innerHTML = `
            <h3>${method} ${path}</h3>
            ${method === 'POST' ? `
                <div class="request-body">
                    <textarea placeholder="Request body (JSON)"></textarea>
                </div>
            ` : ''}
            <button class="btn btn-primary" onclick="APIExplorer.testEndpoint('${path}', '${method}')">
                Testar
            </button>
            <pre class="response" id="response-${path.replace(/\//g, '-')}"></pre>
        `;
    }

    static async testEndpoint(path, method) {
        try {
            const options = {
                method,
                headers: {
                    'Content-Type': 'application/json'
                }
            };

            if (method === 'POST') {
                const body = document.querySelector('.request-body textarea').value;
                options.body = body;
            }

            const response = await fetch(`/api${path}`, options);
            const data = await response.json();
            
            document.getElementById(`response-${path.replace(/\//g, '-')}`).innerHTML = 
                JSON.stringify(data, null, 2);
        } catch (error) {
            console.error('Erro ao testar endpoint:', error);
        }
    }
}

// Blockchain Explorer
class BlockchainExplorer {
    static async search(query) {
        try {
            const response = await fetch(`/api/explorer/search?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            this.renderResults(data);
        } catch (error) {
            console.error('Erro na busca:', error);
        }
    }

    static renderResults(data) {
        const results = document.getElementById('explorer-results');
        results.innerHTML = `
            <div class="result-item">
                <h4>${data.type}</h4>
                <pre><code>${JSON.stringify(data.data, null, 2)}</code></pre>
            </div>
        `;
    }
}

// Inicialização segura
document.addEventListener('DOMContentLoaded', async () => {
    // Remove classes de loading
    document.body.classList.remove('loading');
    
    // Carrega conteúdo dinâmico
    await Promise.all([
        ContentLoader.loadWhitepaper(),
        ContentLoader.loadRoadmap(),
        ContentLoader.loadDocumentation(),
        ContentLoader.loadNodeStatus()
    ]);

    // Inicializa API Explorer
    await APIExplorer.init();

    // Setup do formulário de contato
    const contactForm = document.getElementById('contact-form');
    if (contactForm) {
        contactForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            // Validação básica
            const name = this.querySelector('#name').value.trim();
            const email = this.querySelector('#email').value.trim();
            const message = this.querySelector('#message').value.trim();

            if (!name || !email || !message) {
                alert('Por favor, preencha todos os campos.');
                return;
            }

            // Validação de email
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(email)) {
                alert('Por favor, insira um email válido.');
                return;
            }

            try {
                const formData = new FormData(this);
                const response = await fetch('/api/contact', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        ...addCSRFToken()
                    },
                    body: JSON.stringify(Object.fromEntries(formData))
                });

                if (response.ok) {
                    alert('Mensagem enviada com sucesso!');
                    this.reset();
                } else {
                    throw new Error('Erro ao enviar mensagem.');
                }
            } catch (error) {
                console.error('Erro:', error);
                alert('Erro ao enviar mensagem. Por favor, tente novamente.');
            }
        });
    }

    // Setup do explorador blockchain
    const searchBtn = document.getElementById('search-btn');
    if (searchBtn) {
        searchBtn.addEventListener('click', () => {
            const query = document.getElementById('explorer-search').value;
            if (query) {
                BlockchainExplorer.search(query);
            }
        });
    }
});

// Header responsivo
const header = document.querySelector('.main-header');
let lastScroll = 0;

window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;

    if (currentScroll <= 0) {
        header.classList.remove('scroll-up');
        return;
    }

    if (currentScroll > lastScroll && !header.classList.contains('scroll-down')) {
        header.classList.remove('scroll-up');
        header.classList.add('scroll-down');
    } else if (currentScroll < lastScroll && header.classList.contains('scroll-down')) {
        header.classList.remove('scroll-down');
        header.classList.add('scroll-up');
    }
    lastScroll = currentScroll;
});

// Lazy loading de imagens
if ('loading' in HTMLImageElement.prototype) {
    const images = document.querySelectorAll('img[loading="lazy"]');
    images.forEach(img => {
        img.src = img.dataset.src;
    });
} else {
    // Fallback para browsers que não suportam lazy loading
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/lazysizes/5.3.2/lazysizes.min.js';
    document.body.appendChild(script);
}

// Proteção contra XSS em inputs
function sanitizeInput(input) {
    const div = document.createElement('div');
    div.textContent = input;
    return div.innerHTML;
}

// Proteção contra CSRF
function addCSRFToken() {
    const token = document.querySelector('meta[name="csrf-token"]')?.content;
    if (token) {
        return {
            'X-CSRF-Token': token
        };
    }
    return {};
}

// Sistema de cache para assets
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').then(registration => {
            console.log('ServiceWorker registrado com sucesso.');
        }).catch(error => {
            console.log('Erro no registro do ServiceWorker:', error);
        });
    });
}

// Detecção de conexão offline
window.addEventListener('online', function() {
    document.body.classList.remove('offline');
});

window.addEventListener('offline', function() {
    document.body.classList.add('offline');
});

// Fallback para fontes
document.fonts.ready.then(() => {
    if (!document.fonts.check('1em var(--font-main)')) {
        document.body.classList.add('font-fallback');
    }
});

// Prevenção de ataques de clickjacking
if (window.self !== window.top) {
    window.top.location = window.self.location;
}

// Inicialização segura
document.addEventListener('DOMContentLoaded', function() {
    // Remove classes de loading
    document.body.classList.remove('loading');
    
    // Inicializa tooltips
    const tooltips = document.querySelectorAll('[data-tooltip]');
    tooltips.forEach(tooltip => {
        tooltip.addEventListener('mouseenter', e => {
            const tip = document.createElement('div');
            tip.className = 'tooltip';
            tip.textContent = e.target.dataset.tooltip;
            document.body.appendChild(tip);
            
            const rect = e.target.getBoundingClientRect();
            tip.style.top = rect.bottom + 'px';
            tip.style.left = rect.left + 'px';
        });
        
        tooltip.addEventListener('mouseleave', () => {
            document.querySelector('.tooltip')?.remove();
        });
    });
}); 