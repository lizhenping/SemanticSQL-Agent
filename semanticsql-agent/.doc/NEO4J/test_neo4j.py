# basic_neo4j_test.py
import sys
import time
import random
from neo4j import GraphDatabase
from datetime import datetime, timedelta

class BasicNeo4jTester:
    def __init__(self):
        self.uri = "bolt://localhost:7687"
        self.username = "neo4j"
        self.password = "88888888"
        self.driver = None
        self.success_count = 0
        self.total_tests = 0
    
    def connect(self):
        """建立连接"""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            return True
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False
    
    def test_basic_connection(self):
        """测试基本连接"""
        print("\n" + "="*60)
        print("🔌 测试 1: Neo4j 基本连接")
        print("="*60)
        self.total_tests += 1
        
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 'Hello Neo4j!' as message, datetime() as current_time")
                record = result.single()
                print(f"✅ 连接成功: {record['message']}")
                print(f"   服务器时间: {record['current_time']}")
                
                # 获取Neo4j版本信息
                version_result = session.run("CALL dbms.components() YIELD name, versions, edition")
                for record in version_result:
                    print(f"   📊 {record['name']}: {record['versions'][0]} ({record['edition']})")
                
                self.success_count += 1
                return True
                
        except Exception as e:
            print(f"❌ 基本连接测试失败: {e}")
            return False
    
    def test_create_nodes(self):
        """测试创建节点"""
        print("\n" + "="*60)
        print("➕ 测试 2: 创建节点")
        print("="*60)
        self.total_tests += 1
        
        try:
            with self.driver.session() as session:
                # 清理测试数据
                session.run("MATCH (n:TestPerson) DETACH DELETE n")
                session.run("MATCH (n:TestCompany) DETACH DELETE n")
                
                # 创建人员节点
                people_data = [
                    {"name": "张三", "age": 28, "city": "北京", "department": "技术部"},
                    {"name": "李四", "age": 32, "city": "上海", "department": "产品部"},
                    {"name": "王五", "age": 26, "city": "深圳", "department": "设计部"},
                    {"name": "赵六", "age": 35, "city": "杭州", "department": "技术部"},
                ]
                
                for person in people_data:
                    session.run("""
                    CREATE (p:TestPerson {
                        name: $name, 
                        age: $age, 
                        city: $city, 
                        department: $department,
                        created_at: datetime()
                    })
                    """, **person)
                
                print(f"✅ 成功创建 {len(people_data)} 个人员节点")
                
                # 创建公司节点
                companies = [
                    {"name": "科技有限公司", "industry": "互联网", "size": "大型"},
                    {"name": "创新工作室", "industry": "设计", "size": "小型"},
                ]
                
                for company in companies:
                    session.run("""
                    CREATE (c:TestCompany {
                        name: $name,
                        industry: $industry,
                        size: $size,
                        founded: date('2020-01-01')
                    })
                    """, **company)
                
                print(f"✅ 成功创建 {len(companies)} 个公司节点")
                
                # 验证创建结果
                count_result = session.run("""
                MATCH (p:TestPerson) RETURN count(p) as person_count
                """)
                person_count = count_result.single()['person_count']
                
                count_result = session.run("""
                MATCH (c:TestCompany) RETURN count(c) as company_count
                """)
                company_count = count_result.single()['company_count']
                
                print(f"   📊 验证: {person_count} 个人员, {company_count} 个公司")
                
                self.success_count += 1
                return True
                
        except Exception as e:
            print(f"❌ 创建节点测试失败: {e}")
            return False
    
    def test_create_relationships(self):
        """测试创建关系"""
        print("\n" + "="*60)
        print("🔗 测试 3: 创建关系")
        print("="*60)
        self.total_tests += 1
        
        try:
            with self.driver.session() as session:
                # 创建员工-公司关系
                work_relations = [
                    {"person_name": "张三", "company_name": "科技有限公司", "role": "高级工程师", "salary": 15000},
                    {"person_name": "李四", "company_name": "科技有限公司", "role": "产品经理", "salary": 18000},
                    {"person_name": "王五", "company_name": "创新工作室", "role": "UI设计师", "salary": 12000},
                    {"person_name": "赵六", "company_name": "科技有限公司", "role": "架构师", "salary": 25000},
                ]
                
                for relation in work_relations:
                    session.run("""
                    MATCH (p:TestPerson {name: $person_name})
                    MATCH (c:TestCompany {name: $company_name})
                    CREATE (p)-[:WORKS_FOR {
                        role: $role,
                        salary: $salary,
                        start_date: date('2022-01-01'),
                        created_at: datetime()
                    }]->(c)
                    """, **relation)
                
                print(f"✅ 成功创建 {len(work_relations)} 个工作关系")
                
                # 创建同事关系
                colleague_relations = [
                    {"person1": "张三", "person2": "李四", "project": "AI平台"},
                    {"person1": "张三", "person2": "赵六", "project": "数据分析"},
                ]
                
                for relation in colleague_relations:
                    session.run("""
                    MATCH (p1:TestPerson {name: $person1})
                    MATCH (p2:TestPerson {name: $person2})
                    CREATE (p1)-[:COLLABORATES_WITH {
                        project: $project,
                        since: date('2022-06-01')
                    }]->(p2)
                    """, **relation)
                
                print(f"✅ 成功创建 {len(colleague_relations)} 个协作关系")
                
                # 验证关系创建
                rel_count_result = session.run("""
                MATCH ()-[r]->() RETURN count(r) as total_relationships
                """)
                total_rels = rel_count_result.single()['total_relationships']
                print(f"   📊 验证: 共创建了 {total_rels} 个关系")
                
                self.success_count += 1
                return True
                
        except Exception as e:
            print(f"❌ 创建关系测试失败: {e}")
            return False
    
    def test_query_operations(self):
        """测试查询操作"""
        print("\n" + "="*60)
        print("🔍 测试 4: 查询操作")
        print("="*60)
        self.total_tests += 1
        
        try:
            with self.driver.session() as session:
                # 1. 基本查询
                print("   📋 基本查询测试:")
                result = session.run("""
                MATCH (p:TestPerson)
                RETURN p.name as name, p.age as age, p.city as city
                ORDER BY p.age DESC
                """)
                
                for record in result:
                    print(f"     👤 {record['name']} ({record['age']}岁) - {record['city']}")
                
                # 2. 关系查询
                print("\n   🔗 关系查询测试:")
                result = session.run("""
                MATCH (p:TestPerson)-[r:WORKS_FOR]->(c:TestCompany)
                RETURN p.name as person, r.role as role, r.salary as salary, c.name as company
                ORDER BY r.salary DESC
                """)
                
                for record in result:
                    print(f"     💼 {record['person']} - {record['role']} @ {record['company']} (¥{record['salary']})")
                
                # 3. 聚合查询
                print("\n   📊 聚合查询测试:")
                agg_result = session.run("""
                MATCH (p:TestPerson)-[r:WORKS_FOR]->(c:TestCompany)
                RETURN c.name as company, 
                       count(p) as employee_count,
                       avg(r.salary) as avg_salary,
                       max(r.salary) as max_salary,
                       min(r.salary) as min_salary
                ORDER BY employee_count DESC
                """)
                
                for record in agg_result:
                    print(f"     🏢 {record['company']}: {record['employee_count']}人, "
                          f"平均薪资¥{record['avg_salary']:.0f}, "
                          f"最高¥{record['max_salary']}, 最低¥{record['min_salary']}")
                
                # 4. 条件查询
                print("\n   🎯 条件查询测试 (技术部门):")
                filtered_result = session.run("""
                MATCH (p:TestPerson)-[r:WORKS_FOR]->(c:TestCompany)
                WHERE p.department = '技术部' AND r.salary > 15000
                RETURN p.name as name, p.age as age, r.role as role, r.salary as salary
                ORDER BY r.salary DESC
                """)
                
                for record in filtered_result:
                    print(f"     🎓 {record['name']} ({record['age']}岁) - {record['role']} (¥{record['salary']})")
                
                # 5. 路径查询
                print("\n   🛤️  路径查询测试:")
                path_result = session.run("""
                MATCH path = (p1:TestPerson)-[:COLLABORATES_WITH]-(p2:TestPerson)
                RETURN p1.name as person1, p2.name as person2, length(path) as path_length
                """)
                
                for record in path_result:
                    print(f"     🤝 {record['person1']} <-> {record['person2']} (距离: {record['path_length']})")
                
                self.success_count += 1
                return True
                
        except Exception as e:
            print(f"❌ 查询操作测试失败: {e}")
            return False
    
    def test_update_operations(self):
        """测试更新操作"""
        print("\n" + "="*60)
        print("✏️ 测试 5: 更新操作")
        print("="*60)
        self.total_tests += 1
        
        try:
            with self.driver.session() as session:
                # 1. 更新节点属性
                update_result = session.run("""
                MATCH (p:TestPerson {name: '张三'})
                SET p.age = p.age + 1,
                    p.last_updated = datetime(),
                    p.skills = ['Python', 'Neo4j', 'Machine Learning']
                RETURN p.name as name, p.age as new_age
                """)
                
                record = update_result.single()
                print(f"✅ 节点更新成功: {record['name']} 年龄更新为 {record['new_age']}")
                
                # 2. 更新关系属性
                session.run("""
                MATCH (p:TestPerson {name: '张三'})-[r:WORKS_FOR]->()
                SET r.salary = r.salary + 2000,
                    r.promotion_date = date('2024-01-01'),
                    r.updated_at = datetime()
                """)
                print("✅ 关系属性更新成功: 张三获得加薪")
                
                # 3. 条件批量更新
                batch_update = session.run("""
                MATCH (p:TestPerson)-[r:WORKS_FOR]->(c:TestCompany {name: '科技有限公司'})
                WHERE r.salary < 20000
                SET r.bonus = 5000, r.bonus_date = date('2024-01-01')
                RETURN count(r) as updated_count
                """)
                
                updated_count = batch_update.single()['updated_count']
                print(f"✅ 批量更新成功: {updated_count} 个员工获得奖金")
                
                # 4. 验证更新结果
                verification = session.run("""
                MATCH (p:TestPerson {name: '张三'})-[r:WORKS_FOR]->(c:TestCompany)
                RETURN p.age as age, p.skills as skills, 
                       r.salary as salary, r.bonus as bonus
                """)
                
                record = verification.single()
                print(f"   📊 验证结果:")
                print(f"     年龄: {record['age']}")
                print(f"     技能: {record['skills']}")
                print(f"     薪资: ¥{record['salary']}")
                print(f"     奖金: ¥{record['bonus'] or 0}")
                
                self.success_count += 1
                return True
                
        except Exception as e:
            print(f"❌ 更新操作测试失败: {e}")
            return False
    
    def test_batch_operations(self):
        """测试批量操作"""
        print("\n" + "="*60)
        print("⚡ 测试 6: 批量操作性能")
        print("="*60)
        self.total_tests += 1
        
        try:
            with self.driver.session() as session:
                # 批量插入测试数据
                start_time = time.time()
                batch_size = 1000
                
                # 使用UNWIND进行批量创建
                session.run("""
                UNWIND range(1, $batch_size) as i
                CREATE (p:BatchTest {
                    id: i,
                    name: 'User' + toString(i),
                    email: 'user' + toString(i) + '@example.com',
                    created_at: datetime(),
                    score: toInteger(rand() * 100)
                })
                """, batch_size=batch_size)
                
                create_time = time.time() - start_time
                print(f"✅ 批量创建 {batch_size} 个节点耗时: {create_time:.2f} 秒")
                
                # 批量查询测试
                start_time = time.time()
                query_result = session.run("""
                MATCH (p:BatchTest)
                WHERE p.score > 80
                RETURN count(p) as high_score_count, avg(p.score) as avg_score
                """)
                
                record = query_result.single()
                query_time = time.time() - start_time
                print(f"✅ 条件查询耗时: {query_time:.3f} 秒")
                print(f"   高分用户: {record['high_score_count']} 个")
                print(f"   平均分数: {record['avg_score']:.1f}")
                
                # 批量更新测试
                start_time = time.time()
                update_result = session.run("""
                MATCH (p:BatchTest)
                WHERE p.score > 90
                SET p.level = 'VIP', p.updated_at = datetime()
                RETURN count(p) as vip_count
                """)
                
                update_time = time.time() - start_time
                vip_count = update_result.single()['vip_count']
                print(f"✅ 批量更新 {vip_count} 个VIP用户耗时: {update_time:.3f} 秒")
                
                # 清理批量测试数据
                session.run("MATCH (p:BatchTest) DETACH DELETE p")
                print("✅ 批量测试数据已清理")
                
                self.success_count += 1
                return True
                
        except Exception as e:
            print(f"❌ 批量操作测试失败: {e}")
            return False
    
    def test_csv_import_simulation(self):
        """测试CSV导入模拟"""
        print("\n" + "="*60)
        print("📄 测试 7: CSV导入模拟")
        print("="*60)
        self.total_tests += 1
        
        try:
            with self.driver.session() as session:
                # 模拟CSV数据
                csv_data = [
                    {"id": 1, "name": "产品A", "category": "电子", "price": 1299.99},
                    {"id": 2, "name": "产品B", "category": "服装", "price": 299.50},
                    {"id": 3, "name": "产品C", "category": "电子", "price": 2599.00},
                    {"id": 4, "name": "产品D", "category": "家具", "price": 899.00},
                    {"id": 5, "name": "产品E", "category": "电子", "price": 3999.99},
                ]
                
                # 使用参数化查询批量插入
                for product in csv_data:
                    session.run("""
                    MERGE (p:Product {id: $id})
                    SET p.name = $name,
                        p.category = $category,
                        p.price = $price,
                        p.imported_at = datetime()
                    """, **product)
                
                print(f"✅ 模拟CSV导入 {len(csv_data)} 个产品")
                
                # 按类别统计
                category_stats = session.run("""
                MATCH (p:Product)
                RETURN p.category as category, 
                       count(p) as product_count,
                       avg(p.price) as avg_price,
                       sum(p.price) as total_value
                ORDER BY product_count DESC
                """)
                
                print("   📊 类别统计:")
                for record in category_stats:
                    print(f"     {record['category']}: {record['product_count']}个产品, "
                          f"平均价格¥{record['avg_price']:.2f}, "
                          f"总价值¥{record['total_value']:.2f}")
                
                # 清理产品数据
                session.run("MATCH (p:Product) DELETE p")
                
                self.success_count += 1
                return True
                
        except Exception as e:
            print(f"❌ CSV导入模拟测试失败: {e}")
            return False
    
    def cleanup_all_test_data(self):
        """清理所有测试数据"""
        print("\n" + "="*60)
        print("🧹 清理所有测试数据")
        print("="*60)
        
        try:
            with self.driver.session() as session:
                # 删除所有测试标签的节点
                test_labels = ['TestPerson', 'TestCompany', 'BatchTest', 'Product']
                total_deleted = 0
                
                for label in test_labels:
                    result = session.run(f"MATCH (n:{label}) DETACH DELETE n RETURN count(n) as deleted")
                    deleted = result.single()['deleted']
                    if deleted > 0:
                        print(f"   🗑️  删除了 {deleted} 个 {label} 节点")
                        total_deleted += deleted
                
                print(f"✅ 总共清理了 {total_deleted} 个测试节点")
                
        except Exception as e:
            print(f"⚠️  清理数据时出错: {e}")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始Neo4j基本功能测试")
        print(f"📍 连接信息: {self.uri}")
        print(f"👤 用户名: {self.username}")
        
        if not self.connect():
            print("❌ 无法建立连接，测试终止")
            return False
        
        # 测试列表
        tests = [
            self.test_basic_connection,
            self.test_create_nodes,
            self.test_create_relationships,
            self.test_query_operations,
            self.test_update_operations,
            self.test_batch_operations,
            self.test_csv_import_simulation,
        ]
        
        # 运行所有测试
        for test in tests:
            try:
                test()
                time.sleep(0.5)  # 给数据库一点处理时间
            except Exception as e:
                print(f"❌ 测试 {test.__name__} 执行出错: {e}")
        
        # 清理测试数据
        self.cleanup_all_test_data()
        
        # 关闭连接
        if self.driver:
            self.driver.close()
        
        # 显示结果
        self.show_final_results()
        
        return self.success_count == self.total_tests
    
    def show_final_results(self):
        """显示最终结果"""
        print("\n" + "="*60)
        print("📊 测试结果汇总")
        print("="*60)
        print(f"总测试数: {self.total_tests}")
        print(f"✅ 成功: {self.success_count}")
        print(f"❌ 失败: {self.total_tests - self.success_count}")
        print(f"成功率: {(self.success_count/self.total_tests*100):.1f}%")
        
        if self.success_count == self.total_tests:
            print("\n🎉 所有测试通过！Neo4j基本功能完全正常！")
            print("\n✨ 您现在可以开始使用Neo4j进行数据操作了！")
            print("   💻 Web界面: http://localhost:7474")
            print("   🔌 Python连接: bolt://localhost:7687")
            print("   📚 支持的操作: 创建、查询、更新、删除、批量操作")
        else:
            print("\n⚠️  部分测试失败，请检查错误信息")

def main():
    """主函数"""
    print("Neo4j 基本功能测试工具")
    print("=" * 60)
    
    # 检查Docker容器状态
    try:
        import subprocess
        result = subprocess.run(['docker', 'ps'], capture_output=True, text=True)
        if 'neo4j' not in result.stdout:
            print("⚠️  Neo4j容器似乎未在运行")
            print("请先使用以下命令启动Neo4j:")
            print("docker start neo4j")
            return False
    except:
        print("⚠️  无法检查Docker状态")
    
    # 运行测试
    tester = BasicNeo4jTester()
    success = tester.run_all_tests()
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)