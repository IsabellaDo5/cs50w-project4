addEventListener("DOMContentLoaded", () => {

   /* document.querySelector("#login").onclick = () => {

        username_ = localStorage.setItem("username",document.querySelector("#username").value)
        console.log(username_)
    }*/
    username = document.querySelector(".form-control")
    document.querySelector(".form-control").onkeyup = () => {
        if(username.value.length  > 0 || (username[0] != " "))
        {
            document.querySelector("#register").disabled = false;
        }
        else
        {
            document.querySelector("#register").disabled = true;
        }
    }

});