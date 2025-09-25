CREATE TABLE users (
    id serial primary key,
    nome varchar(50) not null,
    cpf char(11) unique not null
);

CREATE TABLE contas (
    id serial primary key,
    fk_id_user integer not null,
    saldo NUMERIC(12, 2) not null DEFAULT 0.00, -- Tipo correto para dinheiro
    created_at timestamp DEFAULT now(), -- Data de criação (só na inserção)
    updated_at timestamp DEFAULT now(), -- Data da última atualização
    foreign key (fk_id_user) references users(id)
);

INSERT INTO users(nome,cpf) Values ('João','11111111111');
INSERT INTO contas(fk_id_user, saldo) Values (1,25000);


SELECT * 
from users as u join contas on fk_id_user = u.id
where u.cpf = '11111111111'
--Para rodar o python inserir esse codigo no pgAdmin4....rodar cada tabela, e cada insert, depois o select.