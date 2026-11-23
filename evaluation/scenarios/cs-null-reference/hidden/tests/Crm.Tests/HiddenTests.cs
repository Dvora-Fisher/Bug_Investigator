using Crm;
using Xunit;

public class HiddenCustomerServiceTests
{
    [Fact]
    public void UnknownIdGivesPlaceholder() =>
        Assert.Equal(CustomerService.UnknownCustomer, new CustomerService(new InMemoryRepository()).DisplayName(42));

    [Fact]
    public void NameIsTrimmed() =>
        Assert.Equal("Avi", new CustomerService(new InMemoryRepository(new Customer(2, "  Avi "))).DisplayName(2));
}
