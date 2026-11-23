using Crm;
using Xunit;

public class InMemoryRepository(params Customer[] customers) : ICustomerRepository
{
    public Customer? Find(int id) => customers.FirstOrDefault(c => c.Id == id);
}

public class CustomerServiceTests
{
    [Fact]
    public void ExistingCustomerName() =>
        Assert.Equal("Dana Levi", new CustomerService(new InMemoryRepository(new Customer(1, "Dana Levi"))).DisplayName(1));
}
