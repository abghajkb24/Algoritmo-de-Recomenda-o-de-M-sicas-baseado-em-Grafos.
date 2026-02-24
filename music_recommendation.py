from neo4j import GraphDatabase
import json

class MusicRecommender:
    def __init__(self, uri, username, password):
        """Inicializa a conexão com Neo4j"""
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
    
    def close(self):
        """Fecha a conexão"""
        self.driver.close()
    
    def get_recommendations_from_friends(self, user_username, limit=10):
        """Recomenda músicas que amigos do usuário ouvem"""
        query = """
        MATCH (user:User {username: $username})-[:FOLLOWS]->(friend)
          -[:LISTENED_TO {count: count}]->(song:Song)
        WHERE NOT (user)-[:LISTENED_TO]->(song)
        RETURN song.id as id, song.title as title, 
               friend.username as friend_username, count as listen_count
        ORDER BY count DESC
        LIMIT $limit
        """
        
        with self.driver.session() as session:
            result = session.run(query, username=user_username, limit=limit)
            return [dict(record) for record in result]
    
    def get_recommendations_by_favorite_genre(self, user_username, limit=5):
        """Recomenda músicas do gênero favorito do usuário"""
        query = """
        MATCH (user:User {username: $username})-[:LISTENED_TO]->(song:Song)
          -[:BELONGS_TO]->(genre:Genre)
        WITH user, genre, COUNT(song) as genreCount
        ORDER BY genreCount DESC
        LIMIT 1
        MATCH (genre)<-[:BELONGS_TO]-(newSong:Song)
        WHERE NOT (user)-[:LISTENED_TO]->(newSong)
        RETURN newSong.id as id, newSong.title as title, 
               genre.name as genre_name
        LIMIT $limit
        """
        
        with self.driver.session() as session:
            result = session.run(query, username=user_username, limit=limit)
            return [dict(record) for record in result]
    
    def get_combined_recommendations(self, user_username, limit=10):
        """Recomendação híbrida: amigos + gênero favorito"""
        query = """
        MATCH (user:User {username: $username})
        MATCH (user)-[:LISTENED_TO]->(song1:Song)-[:BELONGS_TO]->(genre:Genre)
        WITH user, genre, COUNT(song1) as genreCount
        ORDER BY genreCount DESC
        LIMIT 1
        MATCH (user)-[:FOLLOWS]->(friend)-[:LISTENED_TO]->(song2:Song)
          -[:BELONGS_TO]->(genre)
        WHERE NOT (user)-[:LISTENED_TO]->(song2)
        RETURN DISTINCT song2.id as id, song2.title as title, 
               friend.username as friend_username, 
               genre.name as genre_name, COUNT(friend) as friends_count
        ORDER BY friends_count DESC, song2.title
        LIMIT $limit
        """
        
        with self.driver.session() as session:
            result = session.run(query, username=user_username, limit=limit)
            return [dict(record) for record in result]
    
    def add_listen(self, username, song_id):
        """Registra que um usuário ouviu uma música"""
        query = """
        MATCH (user:User {username: $username}), (song:Song {id: $song_id})
        MERGE (user)-[listen:LISTENED_TO]->(song)
        ON CREATE SET listen.count = 1
        ON MATCH SET listen.count = listen.count + 1
        RETURN listen.count as total_listens
        """
        
        with self.driver.session() as session:
            result = session.run(query, username=username, song_id=song_id)
            record = result.single()
            return record['total_listens'] if record else None
    
    def get_user_profile(self, username):
        """Retorna o perfil do usuário com suas músicas favoritas"""
        query = """
        MATCH (user:User {username: $username})
        OPTIONAL MATCH (user)-[:LISTENED_TO]->(song:Song)-[:BELONGS_TO]->(genre:Genre)
        RETURN user.id as id, user.username as username, user.email as email,
               COLLECT({title: song.title, genre: genre.name}) as favorite_songs
        """
        
        with self.driver.session() as session:
            result = session.run(query, username=username)
            record = result.single()
            return dict(record) if record else None


# Exemplo de uso
if __name__ == "__main__":
    # Conexão com Neo4j
    URI = "bolt://localhost:7687"
    USERNAME = "neo4j"
    PASSWORD = "seu_password_aqui"
    
    recommender = MusicRecommender(URI, USERNAME, PASSWORD)
    
    try:
        # Obter recomendações para Alice
        print("=" * 60)
        print("RECOMENDAÇÕES DE AMIGOS PARA ALICE")
        print("=" * 60)
        friend_recs = recommender.get_recommendations_from_friends("alice")
        for rec in friend_recs:
            print(f"  🎵 {rec['title']} - Ouça por: {rec['friend_username']} ({rec['listen_count']} escutas)")
        
        print("\n" + "=" * 60)
        print("RECOMENDAÇÕES DO GÊNERO FAVORITO")
        print("=" * 60)
        genre_recs = recommender.get_recommendations_by_favorite_genre("alice")
        for rec in genre_recs:
            print(f"  🎵 {rec['title']} ({rec['genre_name']})")
        
        print("\n" + "=" * 60)
        print("RECOMENDAÇÕES COMBINADAS")
        print("=" * 60)
        combined_recs = recommender.get_combined_recommendations("alice")
        for rec in combined_recs:
            print(f"  🎵 {rec['title']} - Amigo: {rec['friend_username']} ({rec['genre_name']})")
        
        print("\n" + "=" * 60)
        print("PERFIL DO USUÁRIO")
        print("=" * 60)
        profile = recommender.get_user_profile("alice")
        print(f"  👤 Usuário: {profile['username']} ({profile['email']})")
        print(f"  Músicas favoritas: {len(profile['favorite_songs'])}")
        for song in profile['favorite_songs']:
            if song['title']:
                print(f"    - {song['title']} ({song['genre']})")
        
        # Adicionar uma escuta
        print("\n" + "=" * 60)
        print("REGISTRANDO UMA NOVA ESCUTA")
        print("=" * 60)
        listens = recommender.add_listen("alice", "song_5")
        print(f"  Alice já ouviu 'God's Plan' {listens} vez(es)")
        
    finally:
        recommender.close()